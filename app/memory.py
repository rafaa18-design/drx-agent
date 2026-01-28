"""Conversation memory management.

Simple in-memory storage for conversation history.
For production, consider using Redis, PostgreSQL, or other persistent storage.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A single message in the conversation."""

    role: str  # 'user' or 'assistant'
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """A conversation with its history and state."""

    conversation_id: str
    messages: list[Message] = field(default_factory=list)
    state: dict[str, Any] = field(default_factory=dict)


class ConversationMemory:
    """In-memory conversation storage.

    Thread-safe for basic operations. For production, use a proper database.
    """

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = defaultdict(
            lambda: Conversation(conversation_id='')
        )

    def get_or_create(self, conversation_id: str) -> Conversation:
        """Get existing conversation or create a new one."""
        if conversation_id not in self._conversations:
            self._conversations[conversation_id] = Conversation(
                conversation_id=conversation_id
            )
        return self._conversations[conversation_id]

    def add_message(
        self, conversation_id: str, role: str, content: str
    ) -> None:
        """Add a message to the conversation."""
        conv = self.get_or_create(conversation_id)
        conv.messages.append(Message(role=role, content=content))

    def get_messages(self, conversation_id: str) -> list[Message]:
        """Get all messages for a conversation."""
        return self.get_or_create(conversation_id).messages

    def get_state(self, conversation_id: str) -> dict[str, Any]:
        """Get the state for a conversation."""
        return self.get_or_create(conversation_id).state

    def update_state(
        self, conversation_id: str, state: dict[str, Any]
    ) -> None:
        """Update the state for a conversation."""
        conv = self.get_or_create(conversation_id)
        conv.state.update(state)

    def clear(self, conversation_id: str) -> None:
        """Clear a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]

    def clear_all(self) -> None:
        """Clear all conversations."""
        self._conversations.clear()


# Global instance
memory = ConversationMemory()
