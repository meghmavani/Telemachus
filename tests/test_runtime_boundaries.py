"""Architectural import-direction boundary between Runtime and Core.

The Runtime coordinates the Core; the Core must remain independent of the
Runtime (docs/runtime.md; ADR-001, "Runtime and Core Separation"). This is
enforced here as a cheap static check over import statements, so the
boundary stays mechanically checkable rather than aspirational as the
tree grows.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "telemachus"

# Packages that are unambiguously Core, in the runtime.md sense: cognition,
# memory, governance, identity, and the tool system. None of these may
# depend on the Runtime that orchestrates them.
CORE_PACKAGES = ("core", "memory", "governance", "cognition", "tools")

# Individual Core-side modules that sit outside those packages but are
# equally Core, not Runtime or CLI: the bootstrap protocol, the cognitive
# pipeline, and the communication engine (interaction/cli_chat.py is the
# CLI half of `interaction/` and legitimately imports the Runtime).
CORE_FILES = (
    "bootstrap.py",
    "pipeline.py",
    "interaction/communication.py",
)

_RUNTIME_IMPORT_RE = re.compile(
    r"^\s*(from\s+telemachus\.runtime\b|import\s+telemachus\.runtime\b)", re.MULTILINE
)


def _find_runtime_import(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    return bool(_RUNTIME_IMPORT_RE.search(text))


@pytest.mark.parametrize("package", CORE_PACKAGES)
def test_core_package_does_not_import_runtime(package: str) -> None:
    """Core, Memory, Governance, Cognition, and Tools must never import Runtime."""
    files = sorted((SRC_ROOT / package).rglob("*.py"))
    assert files, f"expected to find .py files under {package}/"

    offenders = [str(p.relative_to(SRC_ROOT)) for p in files if _find_runtime_import(p)]
    assert not offenders, (
        f"{package}/ must not import telemachus.runtime (ADR-001): {offenders}"
    )


@pytest.mark.parametrize("relative_path", CORE_FILES)
def test_core_file_does_not_import_runtime(relative_path: str) -> None:
    path = SRC_ROOT / relative_path
    assert path.exists(), f"expected {relative_path} to exist"
    assert not _find_runtime_import(path), (
        f"{relative_path} must not import telemachus.runtime (ADR-001)"
    )


def test_runtime_package_may_import_core() -> None:
    """The reverse direction is allowed and expected — confirm it actually works."""
    from telemachus.runtime.lifecycle import RuntimeLifecycle

    assert RuntimeLifecycle is not None


def test_cli_layer_is_allowed_to_import_runtime() -> None:
    """Sanity check that the boundary test isn't accidentally too strict —
    main.py and cli_chat.py are CLI, not Core, and must be free to import
    the Runtime (this is how they delegate lifecycle ownership to it)."""
    main_source = (SRC_ROOT / "main.py").read_text(encoding="utf-8")
    cli_chat_source = (SRC_ROOT / "interaction" / "cli_chat.py").read_text(encoding="utf-8")

    assert _RUNTIME_IMPORT_RE.search(main_source)
    assert _RUNTIME_IMPORT_RE.search(cli_chat_source)
