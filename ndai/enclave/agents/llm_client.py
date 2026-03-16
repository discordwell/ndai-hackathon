"""Claude API client for use inside the enclave.

In production, this routes through vsock proxy with TLS termination
inside the enclave. For development, it uses standard HTTPS.
"""

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when an LLM API call fails."""


class LLMClient:
    """Wrapper around the Anthropic Claude API for agent use."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> anthropic.types.Message:
        """Create a Claude message with optional tool use."""
        # Serialize any non-dict content blocks in message history
        cleaned_messages = self._clean_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": cleaned_messages,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice

        try:
            return self.client.messages.create(**kwargs)
        except anthropic.APIStatusError as e:
            logger.error(f"Claude API error: {e.status_code} {e.message}")
            raise LLMError(f"API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            logger.error(f"Claude API connection error: {e}")
            raise LLMError(f"Connection error: {e}") from e

    def extract_tool_use(
        self, response: anthropic.types.Message
    ) -> dict[str, Any] | None:
        """Extract the first tool use block from a response."""
        for block in response.content:
            if block.type == "tool_use":
                return {"name": block.name, "input": block.input, "id": block.id}
        return None

    def extract_text(self, response: anthropic.types.Message) -> str:
        """Extract text content from a response."""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

    @staticmethod
    def _clean_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure message content is JSON-serializable for the API.

        Claude SDK response.content is a list of ContentBlock objects.
        When stored in conversation history and replayed, these need to
        be converted to dicts.
        """
        cleaned = []
        for msg in messages:
            content = msg.get("content")
            if content is None:
                cleaned.append(msg)
            elif isinstance(content, list):
                serialized = []
                for block in content:
                    if hasattr(block, "model_dump"):
                        serialized.append(block.model_dump())
                    elif isinstance(block, dict):
                        serialized.append(block)
                    else:
                        serialized.append({"type": "text", "text": str(block)})
                cleaned.append({**msg, "content": serialized})
            elif isinstance(content, str):
                cleaned.append(msg)
            else:
                cleaned.append({**msg, "content": str(content)})
        return cleaned
