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


_CODEX_IMPORT_RE = re.compile(
    r"^\s*(from\s+telemachus\.core\.codex\b|import\s+telemachus\.core\.codex\b)",
    re.MULTILINE,
)
_CONSTITUTION_REFERENCE_RE = re.compile(r"\bConstitution\b|\bProtectedConstraint\b")


def test_runtime_does_not_import_codex_or_constitution() -> None:
    """Runtime transports the Constitution BootstrapResult carries — it
    must never parse Codex documents or interpret constitutional policy
    itself (docs/runtime.md; ADR-001). This is stricter than the general
    Core/Runtime import-direction check above: Runtime is allowed to
    depend on Core in general, but this specific dependency (Codex
    parsing, the Constitution type) must not appear in runtime/ at all.
    """
    runtime_root = SRC_ROOT / "runtime"
    files = sorted(runtime_root.rglob("*.py"))
    assert files, "expected to find .py files under runtime/"

    offenders = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        if _CODEX_IMPORT_RE.search(text) or _CONSTITUTION_REFERENCE_RE.search(text):
            offenders.append(str(path.relative_to(SRC_ROOT)))

    assert not offenders, (
        f"runtime/ must not import telemachus.core.codex or reference "
        f"Constitution/ProtectedConstraint: {offenders}"
    )


# ---------------------------------------------------------------------------
# EL-1: the Event Loop must reach Core reasoning only through an opaque
# invoker built by the composition root, never by importing Core pieces
# itself.
# ---------------------------------------------------------------------------

_FORBIDDEN_RUNTIME_IMPORT_RE = re.compile(
    r"^\s*(from\s+telemachus\.(pipeline|wiring|tools)\b"
    r"|import\s+telemachus\.(pipeline|wiring|tools)\b)",
    re.MULTILINE,
)


def test_runtime_does_not_import_pipeline_wiring_or_tools() -> None:
    """The Event Loop dispatches Observations through an opaque callable
    (``telemachus.runtime.event_loop.CoreInvoker``) supplied by
    ``wiring.py``. It must never import the pipeline, the composition
    root, or the tool system directly — doing so would let the Runtime
    reach reasoning or execution on its own rather than through the
    single seam the composition root controls.
    """
    runtime_root = SRC_ROOT / "runtime"
    files = sorted(runtime_root.rglob("*.py"))
    assert files, "expected to find .py files under runtime/"

    offenders = [
        str(p.relative_to(SRC_ROOT))
        for p in files
        if _FORBIDDEN_RUNTIME_IMPORT_RE.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, (
        f"runtime/ must not import telemachus.pipeline, telemachus.wiring, "
        f"or telemachus.tools: {offenders}"
    )


def test_event_loop_observation_reaches_core_as_no_action() -> None:
    """An Observation routed through the Event Loop reaches the Core and
    yields ``ExecutionOutcome.NO_ACTION`` — proof, not assertion, that
    EL-1 is structurally incapable of executing a tool: nothing places
    an ``ActionRequest`` in the pipeline context, so Stage 6 has nothing
    to act on regardless of autonomy level or tool registration.
    """
    from telemachus.core.types import ExecutionOutcome
    from telemachus.pipeline import CognitivePipeline
    from telemachus.runtime.event_loop import EventLoop
    from telemachus.runtime.observations import Observation
    from telemachus.tools.builtin import EchoTool
    from telemachus.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(EchoTool())
    pipeline = CognitivePipeline(tool_registry=registry)

    def invoke(observation: Observation) -> None:
        pipeline.process(
            observation.summary, context={"observation": observation.to_dict()}
        )

    loop = EventLoop(invoke)
    loop.submit(Observation(summary="a routine internal observation"))
    dispatched = loop.tick()

    assert dispatched == 1
    assert pipeline.last_trace is not None
    assert pipeline.last_trace.execution is not None
    assert pipeline.last_trace.execution.outcome is ExecutionOutcome.NO_ACTION
