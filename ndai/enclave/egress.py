"""Egress logging for LLM API calls inside TEE sessions.

Records what was sent/received (by hash) without retaining sensitive data.
Wraps existing LLM clients to intercept create_message() calls.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class EgressEntry:
    """A single logged outbound LLM API call."""
    timestamp: str
    endpoint: str
    method: str
    request_bytes: int
    response_bytes: int
    request_hash: str   # SHA-256 of serialized request
    response_hash: str  # SHA-256 of serialized response


class EgressLog:
    """Accumulator for egress entries within a session."""

    def __init__(self) -> None:
        self.entries: list[EgressEntry] = []

    def record(self, entry: EgressEntry) -> None:
        self.entries.append(entry)

    def to_dict_list(self) -> list[dict[str, Any]]:
        return [
            {
                "timestamp": e.timestamp,
                "endpoint": e.endpoint,
                "method": e.method,
                "request_bytes": e.request_bytes,
                "response_bytes": e.response_bytes,
                "request_hash": e.request_hash,
                "response_hash": e.response_hash,
            }
            for e in self.entries
        ]


def _sha256_of(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class EgressAwareLLMClient:
    """Wraps an LLM client to log egress for every create_message() call.

    Compatible with both LLMClient (Anthropic) and OpenAILLMClient.
    """

    def __init__(self, wrapped_client: Any, egress_log: EgressLog) -> None:
        self._client = wrapped_client
        self._log = egress_log

    @property
    def model(self) -> str:
        return self._client.model

    def create_message(self, **kwargs: Any) -> Any:
        """Intercept create_message, log request/response hashes."""
        # Determine endpoint from client type
        client_type = type(self._client).__name__
        if "openai" in client_type.lower():
            endpoint = "api.openai.com/v1/chat/completions"
        else:
            endpoint = "api.anthropic.com/v1/messages"

        # Serialize request for hashing
        request_str = json.dumps(
            {k: str(v) for k, v in kwargs.items()},
            sort_keys=True,
            separators=(",", ":"),
        )
        request_bytes = len(request_str.encode("utf-8"))
        request_hash = _sha256_of(request_str)

        # Forward the call
        response = self._client.create_message(**kwargs)

        # Serialize response for hashing
        response_str = str(response)
        response_bytes = len(response_str.encode("utf-8"))
        response_hash = _sha256_of(response_str)

        self._log.record(EgressEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            endpoint=endpoint,
            method="POST",
            request_bytes=request_bytes,
            response_bytes=response_bytes,
            request_hash=request_hash,
            response_hash=response_hash,
        ))

        return response

    def extract_text(self, response: Any) -> str:
        return self._client.extract_text(response)

    def extract_tool_use(self, response: Any) -> Any:
        return self._client.extract_tool_use(response)
