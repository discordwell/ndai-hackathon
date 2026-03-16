"""Claude API client for use inside the enclave.

In production, this routes through vsock proxy with TLS termination
inside the enclave. For development, it uses standard HTTPS.
"""

from typing import Any

import anthropic


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
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
        return self.client.messages.create(**kwargs)

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
