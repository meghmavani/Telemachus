"""LLM access for Telemachus.

The Core reasons; this package is how it gets a model to reason *with*.
Everything here is optional: if no candidates are configured, Telemachus
still boots and runs, it just answers deterministically.
"""

from telemachus.llm.router import (
    AllCandidatesFailedError,
    Completion,
    LLMRouter,
    Message,
)

__all__ = [
    "AllCandidatesFailedError",
    "Completion",
    "LLMRouter",
    "Message",
]
