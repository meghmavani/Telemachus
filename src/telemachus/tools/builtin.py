"""Built-in tools shipped with Telemachus.

``EchoTool`` is the minimal tool the composition root registers by
default. It exists to prove the Stage 6 execution boundary end-to-end
(lookup, permission, validation, invocation, trust tracking) without any
external effect — it is PASSIVE, reversible, touches no sacred domain,
and requires no approval.
"""

from __future__ import annotations

from typing import Any

from telemachus.tools.base import Tool, ToolCategory, ToolResult


class EchoTool(Tool):
    """Returns its ``text`` argument unchanged.

    The smallest possible tool: no external effect, no state beyond its
    own trust score, deterministic and side-effect-free.
    """

    def __init__(self) -> None:
        super().__init__(
            name="echo",
            description="Returns the given text unchanged.",
            category=ToolCategory.PASSIVE,
            requires_approval=False,
            reversible=True,
        )

    def validate(self, **kwargs: Any) -> bool:
        """Require a non-empty string ``text`` argument."""
        text = kwargs.get("text")
        return isinstance(text, str) and len(text) > 0

    def execute(self, **kwargs: Any) -> ToolResult:
        """Return ``text`` as the output."""
        return ToolResult.ok(output=kwargs["text"])
