"""Enclave-side main application for NDAI negotiation.

Runs INSIDE the Nitro Enclave. Listens on AF_VSOCK port 5000 for
negotiation requests from the parent EC2 instance, executes the
negotiation using VsockLLMClient (which proxies Claude API calls back
to the parent on port 5001), and sends results back.

The enclave has NO network access. All external communication goes
through AF_VSOCK:
    Port 5000: Command channel (parent -> enclave)
    Port 5001: LLM proxy   (enclave -> parent)

Protocol:
    Length-prefixed framing: 4-byte big-endian length header + JSON payload.
    This matches the existing NitroEnclaveProvider protocol.

Lifecycle:
    1. Parent launches enclave via nitro-cli
    2. Enclave boots and starts this app
    3. Parent sends negotiation request on port 5000
    4. Enclave runs NegotiationSession (LLM calls go out on port 5001)
    5. Enclave sends result back on same port 5000 connection
    6. Enclave waits for next request (or parent terminates it)
"""

import json
import logging
import socket
import struct
import sys
import traceback
from dataclasses import asdict
from typing import Any

from ndai.enclave.agents.base_agent import InventionSubmission
from ndai.enclave.negotiation.engine import SecurityParams
from ndai.enclave.session import NegotiationSession, SessionConfig
from ndai.enclave.vsock_llm_client import VsockLLMClient

logger = logging.getLogger(__name__)

# vsock constants
AF_VSOCK = 40
VMADDR_CID_ANY = 0xFFFFFFFF  # 4294967295 — accept from any CID
COMMAND_PORT = 5000

# Maximum request payload (16 MiB)
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024


# ---------------------------------------------------------------------------
# Patching NegotiationSession to use the vsock LLM client
# ---------------------------------------------------------------------------

class EnclaveNegotiationSession(NegotiationSession):
    """NegotiationSession variant that uses VsockLLMClient instead of LLMClient.

    The parent EC2 instance holds the API key and proxies Claude API calls.
    Inside the enclave we never see the key — we just route requests over
    vsock port 5001.
    """

    def __init__(self, config: SessionConfig):
        # Skip the parent __init__ and wire up ourselves with VsockLLMClient
        from ndai.enclave.agents.buyer_agent import BuyerAgent
        from ndai.enclave.agents.seller_agent import SellerAgent
        from ndai.enclave.negotiation.engine import (
            compute_theta,
            security_capacity,
        )
        from ndai.enclave.session import SessionTranscript

        self.config = config
        self.phi = security_capacity(config.security_params)
        self.theta = compute_theta(config.invention.outside_option_value)
        self.transcript = SessionTranscript()

        # Use vsock LLM client instead of direct Anthropic client
        llm = VsockLLMClient(model=config.anthropic_model)

        self.seller_agent = SellerAgent(
            invention=config.invention,
            llm_client=llm,
            security_threshold=self.phi,
        )
        self.buyer_agent = BuyerAgent(
            budget_cap=config.budget_cap,
            theta=self.theta,
            llm_client=llm,
        )


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

def _parse_negotiation_request(data: dict[str, Any]) -> SessionConfig:
    """Parse a negotiation request into a SessionConfig.

    Expected request format:
    {
        "action": "negotiate",
        "invention": {
            "title": "...",
            "full_description": "...",
            "technical_domain": "...",
            "novelty_claims": [...],
            "prior_art_known": [...],
            "potential_applications": [...],
            "development_stage": "...",
            "self_assessed_value": 0.7,
            "outside_option_value": 0.3,
            "confidential_sections": [...],
            "max_disclosure_fraction": 1.0
        },
        "budget_cap": 0.5,
        "security_params": {"k": 3, "p": 0.5, "c": 1.0, "gamma": 1.0},
        "max_rounds": 5,
        "anthropic_model": "claude-sonnet-4-20250514"
    }

    Note: anthropic_api_key is NOT included — the enclave never sees it.
    The VsockLLMClient routes through the parent proxy which holds the key.
    """
    inv_data = data["invention"]
    invention = InventionSubmission(
        title=inv_data["title"],
        full_description=inv_data["full_description"],
        technical_domain=inv_data["technical_domain"],
        novelty_claims=inv_data["novelty_claims"],
        prior_art_known=inv_data.get("prior_art_known", []),
        potential_applications=inv_data.get("potential_applications", []),
        development_stage=inv_data["development_stage"],
        self_assessed_value=float(inv_data["self_assessed_value"]),
        outside_option_value=float(inv_data["outside_option_value"]),
        confidential_sections=inv_data.get("confidential_sections", []),
        max_disclosure_fraction=float(inv_data.get("max_disclosure_fraction", 1.0)),
    )

    sp_data = data["security_params"]
    security_params = SecurityParams(
        k=int(sp_data["k"]),
        p=float(sp_data["p"]),
        c=float(sp_data["c"]),
        gamma=float(sp_data.get("gamma", 1.0)),
    )

    return SessionConfig(
        invention=invention,
        budget_cap=float(data["budget_cap"]),
        security_params=security_params,
        max_rounds=int(data.get("max_rounds", 5)),
        anthropic_api_key="",  # Never sent into the enclave
        anthropic_model=data.get("anthropic_model", "claude-sonnet-4-20250514"),
    )


def _serialize_result(result: Any) -> dict[str, Any]:
    """Serialize a NegotiationResult to a JSON-safe dict."""
    d = asdict(result)
    # Convert enums to their string values
    if "outcome" in d and hasattr(result.outcome, "value"):
        d["outcome"] = result.outcome.value
    return d


# ---------------------------------------------------------------------------
# vsock I/O helpers
# ---------------------------------------------------------------------------

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


def _read_frame(conn: socket.socket) -> dict[str, Any]:
    """Read a length-prefixed JSON frame."""
    length_bytes = _recv_exact(conn, 4)
    length = struct.unpack(">I", length_bytes)[0]

    if length > MAX_PAYLOAD_BYTES:
        raise ValueError(f"Payload too large: {length} bytes (max {MAX_PAYLOAD_BYTES})")

    payload_bytes = _recv_exact(conn, length)
    return json.loads(payload_bytes.decode("utf-8"))


def _write_frame(conn: socket.socket, data: dict[str, Any]) -> None:
    """Write a length-prefixed JSON frame."""
    payload = json.dumps(data).encode("utf-8")
    frame = struct.pack(">I", len(payload)) + payload
    conn.sendall(frame)


# ---------------------------------------------------------------------------
# Request dispatch
# ---------------------------------------------------------------------------

def _handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a single request and return the response dict."""
    action = request.get("action")

    if action == "negotiate":
        return _handle_negotiate(request)
    elif action == "get_attestation":
        return _handle_attestation(request)
    elif action == "ping":
        return {"status": "ok", "action": "pong"}
    else:
        return {"status": "error", "error": f"Unknown action: {action}"}


def _handle_negotiate(request: dict[str, Any]) -> dict[str, Any]:
    """Run a full negotiation and return the result."""
    try:
        config = _parse_negotiation_request(request)
    except (KeyError, ValueError, TypeError) as exc:
        logger.error("Invalid negotiation request: %s", exc)
        return {
            "status": "error",
            "error": f"Invalid request: {exc}",
        }

    logger.info(
        "Starting negotiation: invention=%s, budget_cap=%.4f, max_rounds=%d",
        config.invention.title,
        config.budget_cap,
        config.max_rounds,
    )

    try:
        session = EnclaveNegotiationSession(config)
        result = session.run()
    except Exception as exc:
        logger.exception("Negotiation failed")
        return {
            "status": "error",
            "error": "Negotiation failed. Check enclave logs for details.",
        }

    result_dict = _serialize_result(result)
    logger.info("Negotiation complete: outcome=%s", result_dict.get("outcome"))
    return {
        "status": "ok",
        "result": result_dict,
    }


def _handle_attestation(request: dict[str, Any]) -> dict[str, Any]:
    """Generate an attestation document.

    Uses the Nitro Security Module (NSM) device at /dev/nsm when available.
    Falls back to a stub for development.
    """
    nonce_hex = request.get("nonce")

    try:
        # Try the real NSM device (only available inside a Nitro Enclave)
        import ctypes
        import ctypes.util

        nsm_lib = ctypes.util.find_library("nsm")
        if nsm_lib:
            logger.info("Generating attestation via NSM (nonce=%s)", nonce_hex)
            # In production this would call the NSM C library
            # For now return a placeholder indicating NSM is available
            return {
                "status": "ok",
                "attestation": "nsm_attestation_placeholder",
                "nonce": nonce_hex,
            }
    except Exception:
        pass

    # Stub attestation for development/testing
    logger.warning("NSM not available — returning stub attestation")
    return {
        "status": "ok",
        "attestation": "stub_attestation_no_nsm",
        "nonce": nonce_hex,
    }


# ---------------------------------------------------------------------------
# Main server loop
# ---------------------------------------------------------------------------

def serve(port: int = COMMAND_PORT) -> None:
    """Main enclave entry point.

    Binds to AF_VSOCK and processes requests sequentially. Each connection
    carries exactly one request/response pair (matching the NitroEnclaveProvider
    protocol where the parent opens a new connection per message).
    """
    server = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((VMADDR_CID_ANY, port))
    server.listen(4)
    logger.info("Enclave app listening on vsock port %d", port)

    while True:
        try:
            conn, addr = server.accept()
            logger.info("Accepted connection from CID=%s port=%s", *addr)
        except OSError:
            logger.exception("Error accepting vsock connection")
            continue

        try:
            conn.settimeout(600)  # 10 min — negotiations can take a while
            request = _read_frame(conn)
            response = _handle_request(request)
            _write_frame(conn, response)
        except Exception:
            logger.exception("Error handling request from CID=%s", addr[0])
            try:
                _write_frame(conn, {"status": "error", "error": "Internal enclave error"})
            except Exception:
                pass
        finally:
            conn.close()


def main() -> None:
    """CLI entry point for the enclave application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )
    logger.info("NDAI Enclave Application starting")

    port = COMMAND_PORT
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid port: %s", sys.argv[1])
            sys.exit(1)

    try:
        serve(port)
    except KeyboardInterrupt:
        logger.info("Enclave app shutting down")
    except Exception:
        logger.exception("Fatal error in enclave app")
        sys.exit(1)


if __name__ == "__main__":
    main()
