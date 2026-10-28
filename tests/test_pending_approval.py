"""Tests for pending approval requests and request-bound challenge matching.

A pending request is not an authorization, and a matching challenge does
not prove human identity, presence or approval (GOV-ADR-001).
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import inspect
import json
import re
from pathlib import Path
from typing import Any

import pytest

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance import pending_approval as module
from telemachus.governance.authorization import (
    CanonicalizationError,
    canonical_action_bytes,
    compute_action_digest,
)
from telemachus.governance.pending_approval import (
    CreatedPendingApproval,
    PendingApprovalRequest,
    challenge_matches,
    create_pending_approval,
    generate_challenge,
)

P1 = ProtectedConstraint.CONSTITUTION_INTEGRITY
P2 = ProtectedConstraint.HUMAN_MEANING
P3 = ProtectedConstraint.RELATIONSHIP_INTEGRITY
P4 = ProtectedConstraint.RESOURCE_AUTHORIZATION
P5 = ProtectedConstraint.HUMAN_AUTHORITY_LIFE_IMPACTING

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "telemachus"
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
FIXED = "ABCDEFGH"

ACTION: dict[str, Any] = {
    "tool_name": "echo",
    "tool_version": "1.0.0",
    "arguments": {"text": "hi", "count": 2},
    "impact": frozenset({P4}),
}


def _create(
    *, now: float = 1_000.0, challenge: str = FIXED, **overrides: Any
) -> CreatedPendingApproval:
    action = {**ACTION, **overrides}
    return create_pending_approval(
        **action, now=now, challenge_source=lambda: challenge
    )


def _rebuild(request: PendingApprovalRequest, **overrides: Any) -> PendingApprovalRequest:
    """Construct a record directly, bypassing create_pending_approval()."""
    fields = {f.name: getattr(request, f.name) for f in dataclasses.fields(request)}
    fields.update(overrides)
    return PendingApprovalRequest(**fields)


def _hand_built(
    binding: bytes, impact: frozenset[ProtectedConstraint] = frozenset()
) -> PendingApprovalRequest:
    """A record whose digest correctly matches ``binding``, so that only the
    structural and canonical-form checks can reject it."""
    return _rebuild(
        _create().request,
        canonical_binding=binding,
        action_digest=hashlib.sha256(binding).hexdigest(),
        impact=impact,
    )


def _binding_doc(
    *,
    arguments: bytes = b"{}",
    fmt: bytes = b"1",
    impact: bytes = b"[]",
    tool: bytes = b'{"name":"t","version":"1"}',
) -> bytes:
    """Canonical-looking binding bytes (keys in sorted order) with overrides."""
    return (
        b'{"arguments":' + arguments + b',"binding_format":' + fmt
        + b',"impact":' + impact + b',"tool":' + tool + b"}"
    )


def _imports(path: Path) -> set[str]:
    """Every module named by an ``import`` or ``from ... import`` statement.

    ``from a.b import c`` yields both ``a.b`` and ``a.b.c``.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


MODULE_PATH = SRC_ROOT / "governance" / "pending_approval.py"


# ---------------------------------------------------------------------------
# Canonical binding
# ---------------------------------------------------------------------------


class TestCanonicalBinding:
    def test_digest_matches_existing_implementation(self) -> None:
        request = _create().request
        assert request.action_digest == compute_action_digest(**ACTION)
        assert request.canonical_binding == canonical_action_bytes(**ACTION)
        assert request.action_digest == hashlib.sha256(request.canonical_binding).hexdigest()

    @pytest.mark.parametrize(
        "overrides",
        [
            {"tool_name": "other"},
            {"tool_version": "2.0.0"},
            {"arguments": {"text": "hi", "count": 3}},
            {"arguments": {"text": "hi"}},
            {"impact": frozenset({P4, P1})},
            {"impact": frozenset()},
        ],
    )
    def test_each_component_changes_the_digest(self, overrides: dict[str, Any]) -> None:
        assert _create(**overrides).request.action_digest != _create().request.action_digest

    def test_key_order_does_not_matter(self) -> None:
        a = _create(arguments={"a": 1, "b": {"x": 1, "y": 2}}).request
        b = _create(arguments={"b": {"y": 2, "x": 1}, "a": 1}).request
        assert a.action_digest == b.action_digest
        assert a.canonical_binding == b.canonical_binding

    @pytest.mark.parametrize(
        "arguments", [{"x": object()}, {"x": (1, 2)}, {"x": float("nan")}, {"x": b"b"}]
    )
    def test_unsupported_arguments_fail_per_canonicalization_contract(
        self, arguments: dict[str, Any]
    ) -> None:
        with pytest.raises(CanonicalizationError):
            _create(arguments=arguments)

    @pytest.mark.parametrize("tool_name", ["", None])
    def test_invalid_tool_identity_fails(self, tool_name: Any) -> None:
        with pytest.raises(CanonicalizationError):
            _create(tool_name=tool_name)

    def test_record_is_frozen(self) -> None:
        request = _create().request
        with pytest.raises(dataclasses.FrozenInstanceError):
            request.action_digest = "0" * 64  # type: ignore[misc]
        created = _create()
        with pytest.raises(dataclasses.FrozenInstanceError):
            created.challenge = "XXXXXXXX"  # type: ignore[misc]

    def test_mutable_inputs_cannot_mutate_the_request(self) -> None:
        arguments = {"text": "hi", "nested": {"k": 1}}
        impact = {P4}
        request = create_pending_approval(
            tool_name="echo",
            tool_version="1.0.0",
            arguments=arguments,
            impact=frozenset(impact),
            now=1.0,
            challenge_source=lambda: FIXED,
        ).request
        before = (request.canonical_binding, request.action_digest, request.impact)

        arguments["text"] = "changed"
        arguments["nested"]["k"] = 99
        impact.add(P1)

        assert (request.canonical_binding, request.action_digest, request.impact) == before
        assert request.arguments == {"text": "hi", "nested": {"k": 1}}

    def test_exposed_state_is_immutable(self) -> None:
        request = _create().request
        assert type(request.canonical_binding) is bytes
        assert isinstance(request.impact, frozenset)
        request.arguments["text"] = "tampered"  # a copy; the record is unaffected
        assert request.arguments["text"] == "hi"

    def test_display_properties_come_from_the_binding(self) -> None:
        request = _create().request
        assert (request.tool_name, request.tool_version) == ("echo", "1.0.0")
        assert request.arguments == {"text": "hi", "count": 2}


class TestRecordValidation:
    def test_inconsistent_digest_rejected(self) -> None:
        request = _create().request
        with pytest.raises(ValueError, match="action_digest"):
            _rebuild(request, action_digest="0" * 64)

    def test_inconsistent_impact_rejected(self) -> None:
        request = _create().request
        with pytest.raises(ValueError, match="impact"):
            _rebuild(request, impact=frozenset({P1}))

    @pytest.mark.parametrize(
        "binding",
        [
            b"not json",
            b"[]",
            b'{"arguments":{},"binding_format":1,"impact":[],"tool":{"name":"t"}}',
            b'{"arguments":{},"binding_format":2,"impact":[],"tool":{"name":"t","version":"1"}}',
            b'{"arguments":{},"binding_format":1,"impact":["nope"],"tool":{"name":"t","version":"1"}}',
            b'{"arguments":{},"binding_format":1,"impact":[],"tool":{"name":"t","version":"1"},"x":1}',
            b'{"arguments":{},"arguments":{},"binding_format":1,"impact":[],"tool":{"name":"t","version":"1"}}',
            b'{"arguments":{"a":NaN},"binding_format":1,"impact":[],"tool":{"name":"t","version":"1"}}',
            # Valid JSON and structure, but not in canonical form (spaces, key order).
            b'{ "tool": {"name":"t","version":"1"}, "arguments": {}, "binding_format": 1, "impact": [] }',
        ],
    )
    def test_invalid_or_non_canonical_binding_rejected(self, binding: bytes) -> None:
        request = _create().request
        digest = hashlib.sha256(binding).hexdigest()
        with pytest.raises(ValueError):
            _rebuild(request, canonical_binding=binding, action_digest=digest, impact=frozenset())

    def test_mutable_byte_buffer_rejected(self) -> None:
        request = _create().request
        with pytest.raises(ValueError, match="bytes"):
            _rebuild(request, canonical_binding=bytearray(request.canonical_binding))

    @pytest.mark.parametrize(
        "overrides",
        [
            {"request_id": ""},
            {"request_id": "   "},
            {"challenge_commitment": "short"},
            {"challenge_commitment": "A" * 64},
            {"action_digest": "short"},
            {"impact": {P4}},
            {"created_at": float("nan")},
            {"created_at": True},
            {"created_at": "now"},
        ],
    )
    def test_malformed_fields_rejected(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            _rebuild(_create().request, **overrides)


class TestHostileBindings:
    """Hand-built records whose digest matches their bytes, so only the
    binding's own validation stands between them and acceptance."""

    def test_the_baseline_document_is_accepted(self) -> None:
        """Guards the helper: a valid canonical document passes."""
        assert _hand_built(_binding_doc()).impact == frozenset()

    @pytest.mark.parametrize("missing", ["arguments", "binding_format", "impact", "tool"])
    def test_missing_top_level_key_rejected(self, missing: str) -> None:
        """The remaining document is otherwise valid compact JSON and its
        digest matches its bytes, so only the structure check can reject it."""
        document = json.loads(_binding_doc())
        del document[missing]
        binding = json.dumps(document, sort_keys=True, separators=(",", ":")).encode("utf-8")
        with pytest.raises(ValueError, match="expected structure"):
            _hand_built(binding)

    @pytest.mark.parametrize(
        "arguments",
        [
            b'{"a":Infinity}',
            b'{"a":-Infinity}',
            b'{"a":NaN}',
            b'{"a":1e400}',  # overflows to infinity without using a literal
            b'{"a":-1e400}',
        ],
    )
    def test_non_finite_numbers_rejected(self, arguments: bytes) -> None:
        with pytest.raises(ValueError):
            _hand_built(_binding_doc(arguments=arguments))

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"arguments": b'{"a":{"b":1,"b":2}}'},
            {"arguments": b'{"a":[{"b":1,"b":2}]}'},
            {"tool": b'{"name":"t","name":"u","version":"1"}'},
        ],
    )
    def test_duplicate_keys_in_nested_objects_rejected(self, kwargs: dict[str, bytes]) -> None:
        with pytest.raises(ValueError, match="duplicate key"):
            _hand_built(_binding_doc(**kwargs))

    @pytest.mark.parametrize("fmt", [b"true", b"1.0", b'"1"', b"0", b"2", b"null"])
    def test_unsupported_binding_format_rejected(self, fmt: bytes) -> None:
        with pytest.raises(ValueError, match="binding_format"):
            _hand_built(_binding_doc(fmt=fmt))

    @pytest.mark.parametrize(
        ("impact_json", "impact"),
        [
            (b'["human_meaning","human_meaning"]', frozenset({P2})),
            (b'["resource_authorization","human_meaning"]', frozenset({P2, P4})),
            (b'["human_meaning","constitution_integrity"]', frozenset({P1, P2})),
            (b'["not_a_constraint"]', frozenset()),
            (b'"human_meaning"', frozenset({P2})),
            (b"[1]", frozenset()),
        ],
    )
    def test_duplicate_or_out_of_order_impact_rejected(
        self, impact_json: bytes, impact: frozenset[ProtectedConstraint]
    ) -> None:
        with pytest.raises(ValueError):
            _hand_built(_binding_doc(impact=impact_json), impact)

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"arguments": b'{"a":"\\u00e9"}'},  # escape instead of the raw character
            {"arguments": b'{"a":"\\u0041"}'},  # even an ASCII letter
            {"arguments": b'{"\\u0061":1}'},  # escaped key
            {"arguments": b'{"a":1.0e0}'},
            {"arguments": b'{"a":1E2}'},
            {"arguments": b'{"a":1e2}'},
            {"arguments": b'{"a":-0}'},
            {"arguments": b'{"a":0.10}'},
            {"arguments": b'{"a": 1}'},  # whitespace
            {"arguments": b'{"b":1,"a":2}'},  # keys not sorted
        ],
    )
    def test_non_canonical_encodings_rejected(self, kwargs: dict[str, bytes]) -> None:
        with pytest.raises(ValueError, match="canonical form"):
            _hand_built(_binding_doc(**kwargs))

    @pytest.mark.parametrize(
        "binding",
        [
            _binding_doc() + b"\n",
            _binding_doc() + b"x",
            b"\xef\xbb\xbf" + _binding_doc(),  # byte-order mark
            b"\xff\xfe",  # not UTF-8
        ],
    )
    def test_trailing_or_undecodable_bytes_rejected(self, binding: bytes) -> None:
        with pytest.raises(ValueError):
            _hand_built(binding)

    def test_excessive_nesting_is_never_accepted(self) -> None:
        """Deep nesting is rejected by the existing canonicalization stack.
        Today that surfaces as RecursionError rather than ValueError, which
        depends on the interpreter's recursion limit, so only fail-closed
        behaviour is asserted, not the exception type."""
        depth = 5000
        nested_binding = _binding_doc(arguments=b'{"a":' + b"[" * depth + b"]" * depth + b"}")
        with pytest.raises((ValueError, RecursionError)):
            _hand_built(nested_binding)

        nested_arguments: dict[str, Any] = {}
        cursor = nested_arguments
        for _ in range(3000):
            cursor["k"] = {}
            cursor = cursor["k"]
        with pytest.raises((ValueError, RecursionError)):
            _create(arguments=nested_arguments)


# ---------------------------------------------------------------------------
# Request creation
# ---------------------------------------------------------------------------


class TestCreation:
    def test_request_ids_are_unique(self) -> None:
        ids = {_create().request.request_id for _ in range(50)}
        assert len(ids) == 50

    def test_creation_timestamp_preserved(self) -> None:
        assert _create(now=1_234.5).request.created_at == 1_234.5

    @pytest.mark.parametrize("now", [float("nan"), float("inf"), True, "now", None])
    def test_invalid_timestamp_rejected(self, now: Any) -> None:
        with pytest.raises(ValueError, match="now"):
            create_pending_approval(
                **ACTION, now=now, challenge_source=lambda: FIXED
            )

    def test_empty_impact_supported(self) -> None:
        request = _create(impact=frozenset()).request
        assert request.impact == frozenset()

    @pytest.mark.parametrize(
        "impact",
        [frozenset({c}) for c in ProtectedConstraint]
        + [frozenset({P1, P4}), frozenset({P2, P3, P5}), frozenset(ProtectedConstraint)],
    )
    def test_every_constraint_and_combination_supported_without_policy(
        self, impact: frozenset[ProtectedConstraint]
    ) -> None:
        request = _create(impact=impact).request
        assert request.impact == impact

    def test_no_authorization_or_eligibility_state_exposed(self) -> None:
        names = {f.name for f in dataclasses.fields(PendingApprovalRequest)}
        assert names == {
            "request_id",
            "created_at",
            "canonical_binding",
            "action_digest",
            "impact",
            "challenge_commitment",
        }
        public = {n for n in dir(PendingApprovalRequest) if not n.startswith("_")}
        assert not {n for n in public if re.search(r"author|approv|eligib|grant", n)}

    def test_result_separates_request_and_challenge(self) -> None:
        created = _create()
        assert isinstance(created.request, PendingApprovalRequest)
        assert created.challenge == FIXED


# ---------------------------------------------------------------------------
# Challenge generation
# ---------------------------------------------------------------------------


class TestChallengeGeneration:
    def test_alphabet_is_32_unambiguous_characters(self) -> None:
        assert len(ALPHABET) == len(set(ALPHABET)) == 32
        assert not set("ILOU") & set(ALPHABET)

    def test_production_challenges_are_eight_alphabet_characters(self) -> None:
        for _ in range(200):
            challenge = generate_challenge()
            assert len(challenge) == 8
            assert set(challenge) <= set(ALPHABET)

    def test_production_generation_uses_secrets(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[str] = []
        real = module.secrets.choice

        def spy(seq: str) -> str:
            calls.append(seq)
            return real(seq)

        monkeypatch.setattr(module.secrets, "choice", spy)
        generate_challenge()
        assert calls == [ALPHABET] * 8

    def test_module_imports_no_predictable_randomness_source(self) -> None:
        """Covers both ``import x`` and ``from x import y`` forms."""
        top_level = {name.split(".")[0] for name in _imports(MODULE_PATH)}
        assert not top_level & {"random", "time", "datetime"}
        assert "secrets" in top_level

    def test_independent_requests_get_fresh_challenges(self) -> None:
        challenges = {
            create_pending_approval(**ACTION, now=1.0).challenge for _ in range(100)
        }
        assert len(challenges) > 95  # 40 bits: collisions are vanishingly unlikely

    def test_default_creation_uses_the_production_generator(self) -> None:
        created = create_pending_approval(**ACTION, now=1.0)
        assert len(created.challenge) == 8 and set(created.challenge) <= set(ALPHABET)
        assert challenge_matches(created.request, created.challenge)

    @pytest.mark.parametrize(
        "bad", ["", "SHORT", "TOOLONGXX", "abcdefgh", "ABCDEFGI", "ABCDEFG ", "ABCDEFG0\n"]
    )
    def test_injected_source_cannot_weaken_the_format(self, bad: str) -> None:
        with pytest.raises(ValueError, match="challenge"):
            _create(challenge=bad)

    def test_non_string_challenge_from_source_rejected(self) -> None:
        with pytest.raises(ValueError, match="challenge"):
            create_pending_approval(**ACTION, now=1.0, challenge_source=lambda: 12345678)  # type: ignore[arg-type, return-value]


# ---------------------------------------------------------------------------
# Commitment and verification
# ---------------------------------------------------------------------------


class TestChallengeMatching:
    def test_correct_response_matches(self) -> None:
        created = _create()
        assert challenge_matches(created.request, FIXED) is True

    @pytest.mark.parametrize(
        "response",
        ["", " ", f" {FIXED}", f"{FIXED} ", f"{FIXED}\n", FIXED.lower(), FIXED[:-1],
         FIXED + "A", "ZZZZZZZZ", FIXED[::-1], None, 12345678, b"ABCDEFGH", ["ABCDEFGH"]],
    )
    def test_everything_else_fails_without_raising(self, response: Any) -> None:
        assert challenge_matches(_create().request, response) is False

    def test_lone_surrogate_response_fails_without_raising(self) -> None:
        assert challenge_matches(_create().request, "\ud800BCDEFGH") is False

    def test_challenge_for_one_request_does_not_validate_against_another(self) -> None:
        first = _create(challenge=FIXED)
        second = _create(challenge=FIXED)  # same text, different request
        assert first.request.request_id != second.request.request_id
        assert first.request.challenge_commitment != second.request.challenge_commitment
        assert challenge_matches(first.request, FIXED)
        assert challenge_matches(second.request, FIXED)
        # A request rebuilt with the other's id no longer accepts the same text.
        moved = _rebuild(first.request, request_id=second.request.request_id)
        assert challenge_matches(moved, FIXED) is False

    def test_plaintext_challenge_absent_from_request(self) -> None:
        created = _create()
        request = created.request
        haystacks = [
            repr(request),
            str(request),
            repr(created),
            repr(dataclasses.asdict(request)),
            request.canonical_binding.decode("utf-8"),
        ]
        assert all(FIXED not in text for text in haystacks)
        assert FIXED not in json.dumps(
            {k: str(v) for k, v in dataclasses.asdict(request).items()}
        )
        assert not any(
            isinstance(getattr(request, f.name), str) and getattr(request, f.name) == FIXED
            for f in dataclasses.fields(request)
        )

    @pytest.mark.parametrize(
        "overrides",
        [
            {"tool_name": "other"},
            {"tool_version": "2.0.0"},
            {"arguments": {"text": "hi", "count": 3}},
            {"impact": frozenset({P4, P1})},
            {"impact": frozenset()},
        ],
    )
    def test_challenge_does_not_validate_against_a_different_action(
        self, overrides: dict[str, Any]
    ) -> None:
        """Same request ID, same commitment, same response text: only the
        action the record is bound to differs. It must no longer match."""
        original = _create()
        other = _create(**overrides).request
        assert other.action_digest != original.request.action_digest
        reattached = _rebuild(
            original.request,
            canonical_binding=other.canonical_binding,
            action_digest=other.action_digest,
            impact=other.impact,
        )
        assert reattached.request_id == original.request.request_id
        assert reattached.challenge_commitment == original.request.challenge_commitment
        assert challenge_matches(original.request, original.challenge) is True
        assert challenge_matches(reattached, original.challenge) is False

    def test_changing_only_the_request_id_invalidates_the_match(self) -> None:
        created = _create()
        renamed = _rebuild(created.request, request_id="another-request-id")
        assert renamed.action_digest == created.request.action_digest
        assert challenge_matches(renamed, created.challenge) is False

    def test_correct_response_still_matches_with_the_digest_bound(self) -> None:
        for _ in range(20):
            created = create_pending_approval(**ACTION, now=1.0)
            assert challenge_matches(created.request, created.challenge) is True

    def test_response_must_be_an_exact_builtin_str(self) -> None:
        """Digits only, so ``str(int(challenge))`` reproduces it exactly: a
        coercing or ``isinstance``-based implementation would accept these."""
        challenge = "23456789"
        created = _create(challenge=challenge)

        class _StrSubclass(str):
            pass

        class _Stringy:
            def __str__(self) -> str:
                return challenge

        assert challenge_matches(created.request, challenge) is True
        assert challenge_matches(created.request, int(challenge)) is False
        assert challenge_matches(created.request, _StrSubclass(challenge)) is False
        assert challenge_matches(created.request, _Stringy()) is False
        # Ordinary string behaviour is unchanged.
        assert challenge_matches(created.request, challenge + "0") is False
        assert challenge_matches(created.request, challenge[:-1]) is False
        assert challenge_matches(created.request, "") is False

    def test_commitment_depends_on_each_component(self) -> None:
        digest = "a" * 64
        base = module._commitment("request-a", digest, FIXED)
        assert re.fullmatch(r"[0-9a-f]{64}", base)
        assert base == module._commitment("request-a", digest, FIXED)
        assert base != module._commitment("request-b", digest, FIXED)
        assert base != module._commitment("request-a", "b" * 64, FIXED)
        assert base != module._commitment("request-a", digest, "ZZZZZZZZ")

    def test_commitment_encoding_is_unambiguous(self) -> None:
        """Every way of splitting the same four characters across the three
        string components yields a distinct commitment."""
        text = "abcd"
        splits = {
            (text[:i], text[i:j], text[j:])
            for i in range(len(text) + 1)
            for j in range(i, len(text) + 1)
        }
        commitments = {module._commitment(*parts) for parts in splits}
        assert len(splits) == 15
        assert len(commitments) == len(splits)

    def test_domain_separation_tag_participates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        before = module._commitment("rid", "a" * 64, FIXED)
        monkeypatch.setattr(module, "_COMMITMENT_DOMAIN", b"some.other.domain")
        assert module._commitment("rid", "a" * 64, FIXED) != before

    def test_comparison_uses_compare_digest(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[bytes, bytes]] = []
        real = module.secrets.compare_digest

        def spy(a: bytes, b: bytes) -> bool:
            calls.append((a, b))
            return real(a, b)

        monkeypatch.setattr(module.secrets, "compare_digest", spy)
        created = _create()
        assert challenge_matches(created.request, FIXED)
        assert len(calls) == 1
        assert calls[0][1] == created.request.challenge_commitment.encode("ascii")

    @pytest.mark.parametrize("function_name", ["challenge_matches", "_commitment"])
    def test_matching_path_does_not_rewrite_input(self, function_name: str) -> None:
        """Located by name, so the check does not depend on where the
        function sits in the file. The behavioural tests above are the
        primary guarantee; this guards against a rewrite being added."""
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        function = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == function_name
        )
        rewriting = {
            "strip", "lstrip", "rstrip", "lower", "upper", "casefold", "title",
            "swapcase", "replace", "translate", "normalize", "removeprefix", "removesuffix",
        }
        called = {
            node.func.attr
            for node in ast.walk(function)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert not called & rewriting
        assert "unicodedata" not in {n.split(".")[0] for n in _imports(MODULE_PATH)}


# ---------------------------------------------------------------------------
# Architectural boundaries
# ---------------------------------------------------------------------------


class TestBoundaries:
    def test_touches_no_authority_or_execution_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from telemachus.core.constitution import Constitution
        from telemachus.governance.grant_ledger import GrantLedger
        from telemachus.governance.grant_verifier import GrantVerifier
        from telemachus.governance.operator import resolve_operator  # noqa: F401
        from telemachus.pipeline import CognitivePipeline
        from telemachus.tools.registry import ToolRegistry

        def _forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("pending approval reached authority or execution code")

        for target, name in (
            (Constitution, "validate_action"),
            (CognitivePipeline, "process"),
            (ToolRegistry, "execute"),
            (ToolRegistry, "get_tool"),
            (GrantLedger, "record"),
            (GrantLedger, "get"),
            (GrantLedger, "consume"),
            (GrantVerifier, "verify_and_consume"),
        ):
            monkeypatch.setattr(target, name, _forbidden)
        monkeypatch.setattr("telemachus.governance.operator.resolve_operator", _forbidden)
        monkeypatch.setattr("telemachus.governance.operator.windows_process_sid", _forbidden)

        created = _create()
        assert challenge_matches(created.request, created.challenge)

    def test_imports_only_stdlib_core_codex_and_authorization(self) -> None:
        own = {name for name in _imports(MODULE_PATH) if name.startswith("telemachus")}
        assert {"telemachus.core.codex", "telemachus.governance.authorization"} <= own
        # ``from x import y`` also yields ``x.y``, so the allowed set lists those too.
        assert own <= {
            "telemachus.core.codex",
            "telemachus.core.codex.ProtectedConstraint",
            "telemachus.governance.authorization",
            "telemachus.governance.authorization.BINDING_FORMAT_VERSION",
            "telemachus.governance.authorization.canonical_action_bytes",
        }

    def test_no_production_module_imports_it(self) -> None:
        offenders = [
            path.relative_to(SRC_ROOT).as_posix()
            for path in sorted(SRC_ROOT.rglob("*.py"))
            if path != MODULE_PATH
            and any(
                name == "telemachus.governance.pending_approval"
                or name.startswith("telemachus.governance.pending_approval.")
                for name in _imports(path)
            )
        ]
        assert not offenders

    def test_runtime_does_not_reference_it(self) -> None:
        offenders = [
            p.relative_to(SRC_ROOT).as_posix()
            for p in sorted((SRC_ROOT / "runtime").rglob("*.py"))
            if "pending_approval" in p.read_text(encoding="utf-8")
        ]
        assert not offenders

    def test_public_api_is_limited_to_the_approved_surface(self) -> None:
        public = {
            name
            for name, value in vars(module).items()
            if not name.startswith("_")
            and (inspect.isclass(value) or inspect.isfunction(value))
            and value.__module__ == module.__name__
        }
        assert public == {
            "PendingApprovalRequest",
            "CreatedPendingApproval",
            "create_pending_approval",
            "challenge_matches",
            "generate_challenge",
        }
