"""Interaction layer — communication, emotional model, and CLI chat."""

from telemachus.interaction.cli_chat import ChatSession
from telemachus.interaction.communication import CommunicationEngine

__all__ = ["CommunicationEngine", "ChatSession"]
