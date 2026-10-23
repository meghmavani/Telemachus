"""Tests for the AuthorizationGrant value type and canonical action binding.

These cover binding semantics only. Nothing here grants authority: the
module is a record type plus pure functions (GOV-ADR-001).
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from telemachus.core.codex import ProtectedConstraint
from telemachus.governance.authorization import (
    AuthorizationGrant,
    CanonicalizationError,
    canonical_action_bytes,
    compute_action_digest,
    is_within_validity_window,
    scope_covers,
)

P1 = ProtectedConstraint.CONSTITUTION_INTEGRITY
P2 = ProtectedConstraint.HUMAN_MEANING
P4 = ProtectedConstraint.RESOURCE_AUTHORIZATION

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "telemachus"


def _digest(**overrides: Any) -> str:
    params: dict[str, Any] = {
        "tool_name": "echo",
        "tool_version": "1.0.0",
        "arguments": {"text": "hi", "count": 2},
        "impact": frozenset({P4}),
    }
    params.update(overrides)
    return compute_action_digest(**params)


def _grant(**overrides: Any) -> AuthorizationGrant:
    fields: dict[str, Any] = {
        "grant_id": "grant-1",
        "principal": "operator",
        "surface": "cli",
        "issued_at": 100.0,
        "expires_at": 200.0,
        "action_digest": _digest(),
        "scope": frozenset({P4}),
    }
    fields.update(overrides)
    return AuthorizationGrant(**fields)


# ---------------------------------------------------------------------------
# Grant value
# ---------------------------------------------------------------------------


class TestGrantValue:
    def test_is_frozen(self) -> None:
        grant = _grant()
        with pytest.raises(dataclasses.FrozenInstanceError):
            grant.principal = "someone else"  # type: ignore[misc]

    def test_fields(self) -> None:
        assert [f.name for f in dataclasses.fields(AuthorizationGrant)] == [
            "grant_id",
            "principal",
            "surface",
            "issued_at",
            "expires_at",
            "action_digest",
            "scope",
        ]

    def test_has_no_consumption_or_authentication_fields(self) -> None:
        names = {f.name for f in dataclasses.fields(AuthorizationGrant)}
        assert not names & {"consumed", "consumed_at", "signature", "token", "secret"}

    def test_scope_uses_protected_constraint_enum(self) -> None:
        grant = _grant(scope=frozenset({P1, P4}))
        assert all(isinstance(c, ProtectedConstraint) for c in grant.scope)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"grant_id": ""},
            {"principal": "   "},
            {"surface": ""},
            {"action_digest": "not-a-digest"},
            {"action_digest": "A" * 64},
            {"scope": {P4}},
            {"scope": frozenset({"resource_authorization"})},
            {"issued_at": float("nan")},
            {"issued_at": True},
        ],
    )
    def test_invalid_construction_rejected(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(ValueError):
            _grant(**overrides)

    @pytest.mark.parametrize("expires_at", [100.0, 50.0])
    def test_expiry_must_be_later_than_issuance(self, expires_at: float) -> None:
        with pytest.raises(ValueError, match="expires_at"):
            _grant(issued_at=100.0, expires_at=expires_at)


# ---------------------------------------------------------------------------
# Canonical digest
# ---------------------------------------------------------------------------


class TestCanonicalDigest:
    def test_identical_inputs_identical_digest(self) -> None:
        assert _digest() == _digest()

    def test_key_order_does_not_matter(self) -> None:
        a = _digest(arguments={"a": 1, "b": {"x": 1, "y": 2}})
        b = _digest(arguments={"b": {"y": 2, "x": 1}, "a": 1})
        assert a == b

    @pytest.mark.parametrize(
        "overrides",
        [
            {"tool_name": "other_tool"},
            {"tool_version": "1.0.1"},
            {"arguments": {"text": "hi", "count": 3}},
            {"arguments": {"text": "hi"}},
            {"arguments": {"text": "hi", "count": 2.0}},
            {"impact": frozenset({P1, P4})},
            {"impact": frozenset()},
        ],
    )
    def test_each_bound_component_changes_digest(self, overrides: dict[str, Any]) -> None:
        assert _digest(**overrides) != _digest()

    def test_impact_order_is_canonical(self) -> None:
        body = canonical_action_bytes(
            tool_name="t", tool_version="1", arguments={}, impact=frozenset({P4, P1, P2})
        )
        assert b'"impact":["constitution_integrity","human_meaning","resource_authorization"]' in body

    def test_description_and_rationale_are_not_inputs(self) -> None:
        with pytest.raises(TypeError):
            compute_action_digest(  # type: ignore[call-arg]
                tool_name="echo",
                tool_version="1.0.0",
                arguments={},
                impact=frozenset(),
                description="shown to the human",
            )
        with pytest.raises(TypeError):
            compute_action_digest(  # type: ignore[call-arg]
                tool_name="echo",
                tool_version="1.0.0",
                arguments={},
                impact=frozenset(),
                rationale="why",
            )

    def test_digest_is_sha256_of_canonical_bytes(self) -> None:
        kwargs: dict[str, Any] = {
            "tool_name": "echo",
            "tool_version": "1.0.0",
            "arguments": {"text": "hi"},
            "impact": frozenset({P4}),
        }
        digest = compute_action_digest(**kwargs)
        assert re.fullmatch(r"[0-9a-f]{64}", digest)
        assert digest == hashlib.sha256(canonical_action_bytes(**kwargs)).hexdigest()

    def test_canonical_bytes_are_explicit(self) -> None:
        body = canonical_action_bytes(
            tool_name="echo", tool_version="1.0.0", arguments={"b": 1, "a": "é"}, impact=frozenset()
        )
        assert body == (
            '{"arguments":{"a":"é","b":1},"binding_format":1,"impact":[],'
            '"tool":{"name":"echo","version":"1.0.0"}}'
        ).encode()

    @pytest.mark.parametrize(
        "arguments",
        [
            {"x": object()},
            {"x": (1, 2)},
            {"x": {1, 2}},
            {"x": b"bytes"},
            {"x": float("nan")},
            {"x": float("inf")},
            {"x": {1: "int key"}},
            {"x": P4},
            {"x": [1, object()]},
        ],
    )
    def test_unsupported_arguments_fail_closed(self, arguments: dict[str, Any]) -> None:
        with pytest.raises(CanonicalizationError):
            _digest(arguments=arguments)

    @pytest.mark.parametrize(
        "overrides",
        [
            {"tool_name": ""},
            {"tool_version": ""},
            {"impact": frozenset({"resource_authorization"})},
        ],
    )
    def test_invalid_identity_or_impact_fail_closed(self, overrides: dict[str, Any]) -> None:
        with pytest.raises(CanonicalizationError):
            _digest(**overrides)

    def test_caller_mapping_is_not_mutated(self) -> None:
        arguments = {"b": 1, "a": 2}
        _digest(arguments=arguments)
        assert list(arguments) == ["b", "a"]


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


class TestScopeCoverage:
    def test_exact_coverage(self) -> None:
        assert scope_covers(frozenset({P1, P4}), frozenset({P1, P4}))

    def test_extra_scope_allowed(self) -> None:
        assert scope_covers(frozenset({P1, P2, P4}), frozenset({P4}))

    def test_partial_coverage_is_false(self) -> None:
        assert not scope_covers(frozenset({P4}), frozenset({P1, P4}))

    def test_empty_impact_is_covered(self) -> None:
        assert scope_covers(frozenset(), frozenset())
        assert scope_covers(frozenset({P4}), frozenset())


# ---------------------------------------------------------------------------
# Validity window
# ---------------------------------------------------------------------------


class TestValidityWindow:
    def test_at_issued_at_is_valid(self) -> None:
        assert is_within_validity_window(_grant(), 100.0)

    def test_before_issued_at_is_invalid(self) -> None:
        assert not is_within_validity_window(_grant(), 99.999)

    def test_at_expires_at_is_invalid(self) -> None:
        assert not is_within_validity_window(_grant(), 200.0)

    def test_just_before_expires_at_is_valid(self) -> None:
        assert is_within_validity_window(_grant(), 199.999)


# ---------------------------------------------------------------------------
# Authority boundary
# ---------------------------------------------------------------------------


class TestAuthorityBoundary:
    def test_constructing_and_evaluating_touches_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Building a grant and running every helper must not validate,
        persist, authorize, or execute anything."""
        from telemachus.core.constitution import Constitution
        from telemachus.memory.store import MemoryStore
        from telemachus.tools.registry import ToolRegistry

        def _forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("authorization value code reached a side effect")

        monkeypatch.setattr(Constitution, "validate_action", _forbidden)
        monkeypatch.setattr(MemoryStore, "store", _forbidden)
        monkeypatch.setattr(ToolRegistry, "execute", _forbidden)
        monkeypatch.setattr(sqlite3, "connect", _forbidden)

        grant = _grant()
        assert scope_covers(grant.scope, frozenset({P4}))
        assert is_within_validity_window(grant, 150.0)

    def test_module_imports_only_stdlib_and_core_codex(self) -> None:
        source = (SRC_ROOT / "governance" / "authorization.py").read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        telemachus_imports = {m for m in imported if m.startswith("telemachus")}
        assert telemachus_imports == {"telemachus.core.codex"}

    def test_runtime_does_not_import_authorization(self) -> None:
        offenders = [
            str(p.relative_to(SRC_ROOT))
            for p in sorted((SRC_ROOT / "runtime").rglob("*.py"))
            if "governance.authorization" in p.read_text(encoding="utf-8")
        ]
        assert not offenders
