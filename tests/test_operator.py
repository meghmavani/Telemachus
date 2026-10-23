"""Tests for operator principal resolution (pinned Windows operator SID).

A match means the process token's account SID equals the configured pin.
It is not authentication of a person and not approval of anything.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

import pytest

from telemachus.config import ConfigError, load_config_from_path
from telemachus.governance import operator as operator_module
from telemachus.governance.operator import (
    OperatorMatch,
    ProcessIdentityError,
    is_well_formed_sid,
    resolve_operator,
    windows_process_sid,
)

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "telemachus"

PINNED = "S-1-5-21-1004336348-1177238915-682003330-1001"
OTHER = "S-1-5-21-1004336348-1177238915-682003330-1002"


def _source(sid: str) -> Any:
    return lambda: sid


def _failing_source() -> str:
    raise ProcessIdentityError("OpenProcessToken failed (Win32 error 5)")


def _write_config(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "telemachus.toml"
    path.write_text(
        "[paths]\n"
        f'data_dir = "{(tmp_path / "data").as_posix()}"\n'
        f'codex_dir = "{(tmp_path / "codex").as_posix()}"\n'
        f'log_dir = "{(tmp_path / "logs").as_posix()}"\n' + extra
    )
    return path


# ---------------------------------------------------------------------------
# Resolution outcomes
# ---------------------------------------------------------------------------


class TestResolveOperator:
    def test_matching_sid(self) -> None:
        result = resolve_operator(PINNED, sid_source=_source(PINNED))
        assert result.status is OperatorMatch.MATCHES_PINNED_OPERATOR
        assert result.matches_pinned_operator is True
        assert result.process_sid == PINNED

    def test_different_sid(self) -> None:
        result = resolve_operator(PINNED, sid_source=_source(OTHER))
        assert result.status is OperatorMatch.DIFFERENT_ACCOUNT
        assert result.matches_pinned_operator is False
        assert result.process_sid == OTHER

    @pytest.mark.parametrize("pin", [None, "", "   "])
    def test_missing_or_blank_pin_fails_closed(self, pin: str | None) -> None:
        called = False

        def source() -> str:
            nonlocal called
            called = True
            return PINNED

        result = resolve_operator(pin, sid_source=source)
        assert result.status is OperatorMatch.NO_OPERATOR_PINNED
        assert result.matches_pinned_operator is False
        assert called is False  # never auto-enrolled from the running account

    @pytest.mark.parametrize(
        "pin",
        ["Revan", "s-1-5-21-1", "S-1-5", "S-1-05-21", f" {PINNED}", "S-1-5-4294967296"],
    )
    def test_malformed_pin_fails_closed(self, pin: str) -> None:
        result = resolve_operator(pin, sid_source=_source(pin))
        assert result.status is OperatorMatch.INVALID_OPERATOR_PIN
        assert result.matches_pinned_operator is False

    def test_lookup_failure_fails_closed(self) -> None:
        result = resolve_operator(PINNED, sid_source=_failing_source)
        assert result.status is OperatorMatch.PROCESS_IDENTITY_UNAVAILABLE
        assert "Win32 error 5" in result.detail
        assert result.matches_pinned_operator is False

    def test_unexpected_lookup_exception_fails_closed(self) -> None:
        def broken() -> str:
            raise ValueError("unexpected")

        result = resolve_operator(PINNED, sid_source=broken)
        assert result.status is OperatorMatch.PROCESS_IDENTITY_UNAVAILABLE

    @pytest.mark.parametrize("bad", ["", "Revan", "S-1-"])
    def test_malformed_process_sid_fails_closed(self, bad: str) -> None:
        result = resolve_operator(PINNED, sid_source=_source(bad))
        assert result.status is OperatorMatch.PROCESS_IDENTITY_UNAVAILABLE

    def test_environment_and_display_names_cannot_override(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """USERNAME/USER and display names are never the identity source."""
        monkeypatch.setenv("USERNAME", PINNED)
        monkeypatch.setenv("USER", PINNED)
        monkeypatch.setenv("LOGNAME", PINNED)
        result = resolve_operator(PINNED, sid_source=_source(OTHER))
        assert result.status is OperatorMatch.DIFFERENT_ACCOUNT

        # A display name such as Identity.creator is not a SID and cannot be a pin.
        assert resolve_operator("Revan", sid_source=_source(PINNED)).status is (
            OperatorMatch.INVALID_OPERATOR_PIN
        )


class TestSidSyntax:
    @pytest.mark.parametrize(
        "sid", [PINNED, "S-1-5-18", "S-1-0-0", "S-1-281474976710655-4294967295"]
    )
    def test_well_formed(self, sid: str) -> None:
        assert is_well_formed_sid(sid)

    @pytest.mark.parametrize(
        "sid",
        ["", "S-1", "S-1-5", "S-2-5-18", "S-1-5-18 ", "S-1-5--18", "S-1-281474976710656-1",
         "S-1-5-" + "-".join(["1"] * 16), None, 42],
    )
    def test_malformed(self, sid: object) -> None:
        assert not is_well_formed_sid(sid)


# ---------------------------------------------------------------------------
# Production identity source
# ---------------------------------------------------------------------------


class TestWindowsProcessSid:
    @pytest.mark.skipif(sys.platform != "win32", reason="requires Windows")
    def test_real_lookup_returns_well_formed_sid(self) -> None:
        assert is_well_formed_sid(windows_process_sid())

    def test_non_windows_reports_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(operator_module.sys, "platform", "linux")
        with pytest.raises(ProcessIdentityError, match="requires Windows"):
            windows_process_sid()
        result = resolve_operator(PINNED)  # default production source
        assert result.status is OperatorMatch.PROCESS_IDENTITY_UNAVAILABLE

    def test_source_does_not_read_environment_or_login_name(self) -> None:
        source = (SRC_ROOT / "governance" / "operator.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        code_names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {
            n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
        }
        assert not code_names & {"environ", "getenv", "getlogin", "getuser"}
        assert "OpenProcessToken" in source and "OpenThreadToken" not in source


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class TestOperatorConfig:
    def test_existing_config_without_section_loads_unpinned(self, tmp_path: Path) -> None:
        config = load_config_from_path(_write_config(tmp_path))
        assert config.authorization.operator_sid == ""
        assert (
            resolve_operator(config.authorization.operator_sid, sid_source=_source(PINNED)).status
            is OperatorMatch.NO_OPERATOR_PINNED
        )

    def test_tracked_config_has_no_pin(self) -> None:
        config = load_config_from_path(SRC_ROOT.parents[1] / "telemachus.toml")
        assert config.authorization.operator_sid == ""

    def test_pinned_sid_loads(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, f'[authorization]\noperator_sid = "{PINNED}"\n')
        assert load_config_from_path(path).authorization.operator_sid == PINNED

    def test_blank_pin_is_unpinned(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, '[authorization]\noperator_sid = ""\n')
        assert load_config_from_path(path).authorization.operator_sid == ""

    @pytest.mark.parametrize("value", ['"Revan"', '"s-1-5-18"', f'" {PINNED}"'])
    def test_malformed_pin_rejected_at_load(self, tmp_path: Path, value: str) -> None:
        path = _write_config(tmp_path, f"[authorization]\noperator_sid = {value}\n")
        with pytest.raises(ConfigError, match="operator_sid"):
            load_config_from_path(path)

    def test_non_string_pin_rejected(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, "[authorization]\noperator_sid = 1001\n")
        with pytest.raises(ConfigError):
            load_config_from_path(path)

    def test_pin_survives_path_resolution_and_log_override(self, tmp_path: Path) -> None:
        path = _write_config(tmp_path, f'[authorization]\noperator_sid = "{PINNED}"\n')
        config = load_config_from_path(path).with_log_level("DEBUG")
        assert config.authorization.operator_sid == PINNED


# ---------------------------------------------------------------------------
# Authority boundary
# ---------------------------------------------------------------------------


class TestAuthorityBoundary:
    def test_resolution_touches_no_grant_or_constitution_code(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from telemachus.core.constitution import Constitution
        from telemachus.governance.grant_ledger import GrantLedger
        from telemachus.governance.grant_verifier import GrantVerifier

        def _forbidden(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError("operator resolution reached grant or constitution code")

        for target, name in (
            (Constitution, "validate_action"),
            (GrantLedger, "record"),
            (GrantLedger, "get"),
            (GrantLedger, "consume"),
            (GrantVerifier, "verify_and_consume"),
        ):
            monkeypatch.setattr(target, name, _forbidden)

        assert resolve_operator(PINNED, sid_source=_source(PINNED)).matches_pinned_operator

    def test_module_imports_no_telemachus_code(self) -> None:
        source = (SRC_ROOT / "governance" / "operator.py").read_text(encoding="utf-8")
        modules: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
            elif isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
        assert not {m for m in modules if m.startswith("telemachus")}

    def test_public_surface(self) -> None:
        public = {n for n in dir(operator_module) if not n.startswith("_")} - {
            "annotations", "re", "sys", "Callable", "dataclass", "Enum"
        }
        assert public == {
            "OperatorMatch",
            "OperatorResolution",
            "ProcessIdentityError",
            "ProcessSidSource",
            "is_well_formed_sid",
            "resolve_operator",
            "windows_process_sid",
        }

    def test_no_production_module_uses_operator_resolution(self) -> None:
        offenders = []
        for path in sorted(SRC_ROOT.rglob("*.py")):
            if path.name == "operator.py":
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                names: list[str] = []
                if isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
                elif isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                if any(n == "telemachus.governance.operator" for n in names):
                    offenders.append(path.relative_to(SRC_ROOT).as_posix())
        assert not offenders
