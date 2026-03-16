"""OpenAI API client as a drop-in replacement for the Anthropic LLMClient.

Translates between the Anthropic tool-calling format used by NDAI agents
and the OpenAI function-calling format. Response objects use lightweight
dataclass wrappers (same pattern as vsock_llm_client.py) so that
extract_tool_use() and extract_text() work identically.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

import openai

logger = logging.getLogger(__name__)


class OpenAILLMError(Exception):
    """Raised when an OpenAI API call fails."""


# ---------------------------------------------------------------------------
# Lightweight response wrappers (mirrors vsock_llm_client.py pattern)
# ---------------------------------------------------------------------------


@dataclass
class ContentBlock:
    """Mimics anthropic.types.ContentBlock (text or tool_use)."""

    type: str
    # Text block fields
    text: str = ""
    # Tool use block fields
    id: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)

    def model_dump(self) -> dict[str, Any]:
        """Serialize to a dict, matching the Anthropic SDK's model_dump()."""
        if self.type == "text":
            return {"type": "text", "text": self.text}
        elif self.type == "tool_use":
            return {"type": "tool_use", "id": self.id, "name": self.name, "input": self.input}
        else:
            return {"type": self.type, "text": self.text}


@dataclass
class OpenAIMessageWrapper:
    """Mimics anthropic.types.Message — the return type of create_message.

    Agents access:
        response.content  -> list[ContentBlock]
    And the OpenAILLMClient helper methods (extract_tool_use, extract_text)
    iterate over response.content looking at .type, .text, .name, .input, .id.
    """

    content: list[ContentBlock]
    stop_reason: str = "end_turn"


# ---------------------------------------------------------------------------
# Format translators
# ---------------------------------------------------------------------------


def _translate_tools_to_openai(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Translate Anthropic tool definitions to OpenAI function-calling format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    openai_tools = []
    for tool in tools:
        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("input_schema", {}),
            },
        })
    return openai_tools


def _translate_tool_choice_to_openai(
    tool_choice: dict[str, Any],
) -> dict[str, Any]:
    """Translate Anthropic tool_choice to OpenAI tool_choice.

    Anthropic: {"type": "tool", "name": "make_disclosure"}
    OpenAI:    {"type": "function", "function": {"name": "make_disclosure"}}

    Anthropic: {"type": "auto"} or {"type": "any"}
    OpenAI:    "auto" or "required"
    """
    choice_type = tool_choice.get("type", "auto")
    if choice_type == "tool":
        return {
            "type": "function",
            "function": {"name": tool_choice["name"]},
        }
    elif choice_type == "any":
        return "required"
    else:
        return "auto"


def _translate_messages_to_openai(
    system: str, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Translate Anthropic-format messages to OpenAI chat format.

    Key differences handled:
    - System message: Anthropic passes separately; OpenAI uses role=system in array.
    - Tool use in assistant messages: Anthropic uses content blocks with type=tool_use;
      OpenAI uses tool_calls array on the message.
    - Tool results: Anthropic uses role=user with content=[{type: tool_result, ...}];
      OpenAI uses role=tool messages.
    """
    openai_messages: list[dict[str, Any]] = []

    # System message first
    if system:
        openai_messages.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content")

        if role == "assistant":
            openai_msg = _translate_assistant_message(content)
            openai_messages.append(openai_msg)

        elif role == "user":
            # Check if content contains tool_result blocks
            if isinstance(content, list):
                tool_result_msgs = _extract_tool_results(content)
                if tool_result_msgs:
                    openai_messages.extend(tool_result_msgs)
                else:
                    # Regular user message with content blocks
                    text_parts = _extract_text_from_blocks(content)
                    openai_messages.append({"role": "user", "content": text_parts})
            elif isinstance(content, str):
                openai_messages.append({"role": "user", "content": content})
            else:
                openai_messages.append({"role": "user", "content": str(content)})
        else:
            # Pass through any other role as-is
            openai_messages.append(msg)

    return openai_messages


def _translate_assistant_message(content: Any) -> dict[str, Any]:
    """Translate an assistant message's content to OpenAI format.

    Anthropic assistant messages can contain mixed text and tool_use blocks.
    OpenAI separates these: text goes in 'content', tool calls go in 'tool_calls'.
    """
    if isinstance(content, str):
        return {"role": "assistant", "content": content}

    if not isinstance(content, list):
        return {"role": "assistant", "content": str(content) if content else ""}

    text_parts = []
    tool_calls = []

    for block in content:
        block_dict = _block_to_dict(block)
        block_type = block_dict.get("type", "text")

        if block_type == "text":
            text_parts.append(block_dict.get("text", ""))
        elif block_type == "tool_use":
            tool_input = block_dict.get("input", {})
            if isinstance(tool_input, str):
                arguments = tool_input
            else:
                arguments = json.dumps(tool_input)
            tool_calls.append({
                "id": block_dict.get("id", ""),
                "type": "function",
                "function": {
                    "name": block_dict.get("name", ""),
                    "arguments": arguments,
                },
            })

    msg: dict[str, Any] = {"role": "assistant"}
    text_content = "\n".join(text_parts) if text_parts else None
    msg["content"] = text_content
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return msg


def _extract_tool_results(blocks: list) -> list[dict[str, Any]]:
    """Extract tool_result blocks and convert to OpenAI role=tool messages."""
    results = []
    for block in blocks:
        block_dict = _block_to_dict(block)
        if block_dict.get("type") == "tool_result":
            content = block_dict.get("content", "")
            if isinstance(content, list):
                # Extract text from nested content blocks
                text_parts = []
                for inner in content:
                    if isinstance(inner, dict) and inner.get("type") == "text":
                        text_parts.append(inner.get("text", ""))
                    elif isinstance(inner, str):
                        text_parts.append(inner)
                content = "\n".join(text_parts)
            elif not isinstance(content, str):
                content = str(content)
            results.append({
                "role": "tool",
                "tool_call_id": block_dict.get("tool_use_id", ""),
                "content": content,
            })
    return results


def _extract_text_from_blocks(blocks: list) -> str:
    """Extract text from a list of content blocks."""
    parts = []
    for block in blocks:
        block_dict = _block_to_dict(block)
        if block_dict.get("type") == "text":
            parts.append(block_dict.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(parts) if parts else ""


def _block_to_dict(block: Any) -> dict[str, Any]:
    """Convert a content block to a dict, handling SDK objects and plain dicts."""
    if isinstance(block, dict):
        return block
    if hasattr(block, "model_dump"):
        return block.model_dump()
    if hasattr(block, "__dict__"):
        return block.__dict__
    return {"type": "text", "text": str(block)}


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_openai_response(response: Any) -> OpenAIMessageWrapper:
    """Parse an OpenAI ChatCompletion response into our wrapper format.

    Converts OpenAI tool_calls and content into the Anthropic-style
    ContentBlock list that agents expect.
    """
    choice = response.choices[0]
    message = choice.message
    blocks: list[ContentBlock] = []

    # Extract text content
    if message.content:
        blocks.append(ContentBlock(type="text", text=message.content))

    # Extract tool calls
    if message.tool_calls:
        for tc in message.tool_calls:
            try:
                tool_input = json.loads(tc.function.arguments)
            except (json.JSONDecodeError, TypeError):
                tool_input = {}
            blocks.append(ContentBlock(
                type="tool_use",
                id=tc.id,
                name=tc.function.name,
                input=tool_input,
            ))

    stop_reason = "end_turn"
    if choice.finish_reason == "tool_calls":
        stop_reason = "tool_use"
    elif choice.finish_reason == "stop":
        stop_reason = "end_turn"

    return OpenAIMessageWrapper(content=blocks, stop_reason=stop_reason)


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------


class OpenAILLMClient:
    """Drop-in replacement for LLMClient that uses the OpenAI API.

    Exposes the same public interface: create_message, extract_tool_use,
    extract_text, and _clean_messages.
    """

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> OpenAIMessageWrapper:
        """Create an OpenAI chat completion with optional function calling."""
        cleaned_messages = self._clean_messages(messages)
        openai_messages = _translate_messages_to_openai(system, cleaned_messages)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_completion_tokens": max_tokens,
            "messages": openai_messages,
        }
        if tools:
            kwargs["tools"] = _translate_tools_to_openai(tools)
        if tool_choice:
            kwargs["tool_choice"] = _translate_tool_choice_to_openai(tool_choice)

        try:
            response = self.client.chat.completions.create(**kwargs)
            return _parse_openai_response(response)
        except openai.APIStatusError as e:
            logger.error(f"OpenAI API error: {e.status_code} {e.message}")
            raise OpenAILLMError(f"API error {e.status_code}: {e.message}") from e
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI API connection error: {e}")
            raise OpenAILLMError(f"Connection error: {e}") from e

    def extract_tool_use(
        self, response: OpenAIMessageWrapper
    ) -> dict[str, Any] | None:
        """Extract the first tool use block from a response."""
        for block in response.content:
            if block.type == "tool_use":
                return {"name": block.name, "input": block.input, "id": block.id}
        return None

    def extract_text(self, response: OpenAIMessageWrapper) -> str:
        """Extract text content from a response."""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

    @staticmethod
    def _clean_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure message content is JSON-serializable for the API.

        Handles ContentBlock objects (both from the Anthropic SDK and our
        wrappers), converting them to plain dicts for transmission.
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
