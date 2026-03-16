"""LLM client that proxies Claude API calls through vsock to the parent instance.

Inside a Nitro Enclave there is no network access. This client serializes
Claude API requests, sends them over AF_VSOCK to the parent-side proxy
(vsock_proxy.py), and deserializes the response into objects compatible
with the standard LLMClient interface that the agents expect.

Protocol:
    Port 5001 (distinct from main command channel on 5000).
    Length-prefixed framing: 4-byte big-endian length header + JSON payload.
    Request:  {"action": "llm_call", "model": ..., "system": ..., ...}
    Response: {"content": [...], "stop_reason": ..., "usage": {...}}
              or {"error": "..."}
"""

import json
import logging
import socket
import struct
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# vsock constants
AF_VSOCK = 40
VMADDR_CID_HOST = 3  # Parent/host CID from enclave's perspective
LLM_PROXY_PORT = 5001


class VsockLLMError(Exception):
    """Raised when a vsock-proxied LLM call fails."""


# ---------------------------------------------------------------------------
# Lightweight response objects that mirror the Anthropic SDK types
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
class Usage:
    """Mimics anthropic.types.Usage."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class VsockMessage:
    """Mimics anthropic.types.Message — the return type of create_message.

    Agents access:
        response.content  -> list[ContentBlock]
        response.stop_reason -> str
    And the LLMClient helper methods (extract_tool_use, extract_text) iterate
    over response.content looking at .type, .text, .name, .input, .id.
    """

    content: list[ContentBlock]
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)

    @classmethod
    def from_api_dict(cls, data: dict[str, Any]) -> "VsockMessage":
        """Construct from the raw API response dict returned by the proxy."""
        blocks: list[ContentBlock] = []
        for block_data in data.get("content", []):
            block_type = block_data.get("type", "text")
            if block_type == "text":
                blocks.append(ContentBlock(type="text", text=block_data.get("text", "")))
            elif block_type == "tool_use":
                blocks.append(ContentBlock(
                    type="tool_use",
                    id=block_data.get("id", ""),
                    name=block_data.get("name", ""),
                    input=block_data.get("input", {}),
                ))
            else:
                blocks.append(ContentBlock(type=block_type, text=block_data.get("text", "")))

        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        )
        return cls(
            content=blocks,
            stop_reason=data.get("stop_reason", "end_turn"),
            usage=usage,
        )


# ---------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------

class VsockLLMClient:
    """Drop-in replacement for LLMClient that routes through vsock proxy.

    Exposes the same public interface: create_message, extract_tool_use,
    extract_text, and _clean_messages.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        parent_cid: int = VMADDR_CID_HOST,
        proxy_port: int = LLM_PROXY_PORT,
    ):
        self.model = model
        self.parent_cid = parent_cid
        self.proxy_port = proxy_port

    # -- vsock transport ---------------------------------------------------

    def _vsock_roundtrip(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON request to the parent proxy and return the response."""
        data = json.dumps(payload).encode("utf-8")
        frame = struct.pack(">I", len(data)) + data

        sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        sock.settimeout(300)  # 5 min — LLM calls can be slow
        try:
            sock.connect((self.parent_cid, self.proxy_port))
            sock.sendall(frame)

            # Read length header
            length_bytes = self._recv_exact(sock, 4)
            length = struct.unpack(">I", length_bytes)[0]

            # Read payload
            response_bytes = self._recv_exact(sock, length)
            return json.loads(response_bytes.decode("utf-8"))
        finally:
            sock.close()

    @staticmethod
    def _recv_exact(sock: socket.socket, nbytes: int) -> bytes:
        """Read exactly nbytes from a socket."""
        buf = b""
        while len(buf) < nbytes:
            chunk = sock.recv(nbytes - len(buf))
            if not chunk:
                raise ConnectionError(
                    f"vsock connection closed after {len(buf)}/{nbytes} bytes"
                )
            buf += chunk
        return buf

    # -- Public API (matches LLMClient) ------------------------------------

    def create_message(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: dict[str, Any] | None = None,
        max_tokens: int = 2048,
    ) -> VsockMessage:
        """Create a Claude message by proxying through the parent instance."""
        # Serialize any non-dict content blocks in message history
        cleaned_messages = self._clean_messages(messages)

        request: dict[str, Any] = {
            "action": "llm_call",
            "model": self.model,
            "system": system,
            "messages": cleaned_messages,
            "max_tokens": max_tokens,
        }
        if tools:
            request["tools"] = tools
        if tool_choice:
            request["tool_choice"] = tool_choice

        logger.debug("Sending LLM request via vsock (model=%s, msg_count=%d)",
                      self.model, len(cleaned_messages))

        try:
            response_dict = self._vsock_roundtrip(request)
        except (ConnectionError, OSError, socket.timeout) as exc:
            logger.error("vsock transport error: %s", exc)
            raise VsockLLMError(f"vsock transport error: {exc}") from exc

        # Check for proxy-side errors
        if "error" in response_dict:
            error_msg = response_dict["error"]
            logger.error("LLM proxy returned error: %s", error_msg)
            raise VsockLLMError(f"LLM proxy error: {error_msg}")

        logger.debug("Received LLM response via vsock (stop_reason=%s)",
                      response_dict.get("stop_reason"))
        return VsockMessage.from_api_dict(response_dict)

    def extract_tool_use(self, response: VsockMessage) -> dict[str, Any] | None:
        """Extract the first tool use block from a response."""
        for block in response.content:
            if block.type == "tool_use":
                return {"name": block.name, "input": block.input, "id": block.id}
        return None

    def extract_text(self, response: VsockMessage) -> str:
        """Extract text content from a response."""
        parts = []
        for block in response.content:
            if block.type == "text":
                parts.append(block.text)
        return "\n".join(parts)

    @staticmethod
    def _clean_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Ensure message content is JSON-serializable.

        Handles ContentBlock objects (both from the Anthropic SDK and our
        VsockMessage), converting them to plain dicts for transmission.
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
