"""Tool system — extensible tool registry with trust tracking and governance.

Tools are extensions of capability, not authority. Every tool must operate
within the Constitution, Autonomy Charter, and sacred domain restrictions.
"""

from telemachus.tools.base import Tool, ToolCategory, ToolResult
from telemachus.tools.registry import ToolRegistry

__all__ = [
    "Tool",
    "ToolCategory",
    "ToolRegistry",
    "ToolResult",
]
