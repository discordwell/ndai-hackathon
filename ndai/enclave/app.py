"""Enclave-side main application for NDAI negotiation.

Runs INSIDE the Nitro Enclave. Listens on AF_VSOCK port 5000 for
negotiation requests from the parent EC2 instance, executes the
negotiation using VsockLLMClient (which proxies Claude API calls back
to the parent on port 5001), and sends results back.

The enclave has NO network access. All external communication goes
through AF_VSOCK:
    Port 5000: Command channel (parent -> enclave)
    Port 5001: LLM proxy   (enclave -> parent) [simulated mode]
    Port 5002: TCP tunnel   (enclave -> parent) [Nitro mode, TLS traffic]

Protocol:
    Length-prefixed framing: 4-byte big-endian length header + JSON payload.
    This matches the existing NitroEnclaveProvider protocol.

Lifecycle:
    1. Parent launches enclave via nitro-cli
    2. Enclave boots and starts this app
    3. Enclave generates ephemeral P-384 keypair
    4. Parent requests attestation (includes ephemeral public key)
    5. Parent verifies attestation, encrypts API key to enclave's public key
    6. Parent delivers encrypted API key
    7. Parent sends negotiation request on port 5000
    8. Enclave runs NegotiationSession (LLM calls go through tunnel on port 5002)
    9. Enclave sends result back on same port 5000 connection
    10. Enclave waits for next request (or parent terminates it)
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
# Enclave-level state (initialized on startup)
# ---------------------------------------------------------------------------

class EnclaveState:
    """Mutable state for the enclave application.

    Holds the ephemeral keypair and decrypted API key across requests.
    Poker table state persists here so deck/cards stay sealed in the enclave.
    """

    def __init__(self):
        self.keypair = None  # EnclaveKeypair, set on startup
        self.api_key: str | None = None  # Decrypted API key, set via deliver_key
        self.nitro_mode: bool = False  # True when real NSM is available
        self.nsm_stub = None  # Cached NSMStub instance for dev mode
        self.poker_tables: dict = {}  # table_id -> TableState (sealed game state)
        self.pending_overlay = None  # BuyerOverlay, set via deliver_overlay

    def initialize(self):
        """Generate ephemeral keypair and detect NSM availability."""
        from ndai.enclave.ephemeral_keys import generate_keypair

        self.keypair = generate_keypair()
        logger.info(
            "Ephemeral keypair generated (%d bytes DER)",
            len(self.keypair.public_key_der),
        )

        # Detect whether we're in a real Nitro Enclave
        from ndai.enclave.nsm import is_nsm_available
        self.nitro_mode = is_nsm_available()
        logger.info("Nitro mode: %s", self.nitro_mode)


# Global enclave state (singleton for the process)
_state = EnclaveState()


# ---------------------------------------------------------------------------
# Patching NegotiationSession to use the vsock LLM client
# ---------------------------------------------------------------------------

class EnclaveNegotiationSession(NegotiationSession):
    """NegotiationSession variant that uses VsockLLMClient instead of LLMClient.

    The parent EC2 instance holds the API key and proxies Claude API calls.
    Inside the enclave we never see the key — we just route requests over
    vsock port 5001.

    In Nitro mode with a delivered API key, uses TunnelOpenAILLMClient
    instead, routing traffic through the encrypted TCP tunnel.
    """

    def __init__(self, config: SessionConfig):
        # Skip the parent __init__ and wire up ourselves with the appropriate LLM client
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

        # Choose LLM client based on mode
        llm = self._create_llm_client(config)

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

    @staticmethod
    def _create_llm_client(config: SessionConfig):
        """Create the appropriate LLM client based on enclave state."""
        # If we have a decrypted API key (Nitro mode with key delivery),
        # use the tunnel client for end-to-end encryption
        if _state.api_key and _state.nitro_mode:
            logger.info("Using TunnelOpenAILLMClient (end-to-end encrypted)")
            from ndai.enclave.tunnel_llm_client import TunnelOpenAILLMClient

            llm_provider = config.llm_provider if hasattr(config, "llm_provider") else "openai"
            model = config.llm_model if hasattr(config, "llm_model") else config.anthropic_model
            return TunnelOpenAILLMClient(api_key=_state.api_key, model=model)

        # Fallback: vsock proxy (parent decrypts and re-encrypts — less secure)
        logger.info("Using VsockLLMClient (vsock proxy mode)")
        return VsockLLMClient(model=config.anthropic_model)


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
        "llm_provider": "openai",
        "llm_model": "gpt-4o",
        "anthropic_model": "claude-sonnet-4-20250514"
    }

    Note: API key is NOT included — it's either delivered via deliver_key
    (Nitro mode) or held by the parent proxy (simulated mode).
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
        llm_provider=data.get("llm_provider", "anthropic"),
        llm_model=data.get("llm_model", data.get("anthropic_model", "claude-sonnet-4-20250514")),
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


# Fields that are safe to send to the untrusted parent.
# Everything else (omega_hat, theta, phi, payoffs, buyer_valuation) stays in the enclave.
_SAFE_RESULT_FIELDS = {"outcome", "final_price", "reason"}

# Map of detailed reason strings to safe generic versions.
# Reason strings may contain numerical values (buyer_valuation, prices,
# alpha_0 * omega_hat) that are supposed to stay confidential.
_SAFE_REASONS: dict[str, str] = {
    "Bilateral Nash bargaining equilibrium reached": "Agreement reached",
    "Nash bargaining equilibrium reached": "Agreement reached",
}


def _sanitize_reason(reason: str | None) -> str | None:
    """Replace reason strings that leak numerical internals with safe versions."""
    if reason is None:
        return None
    # Exact match to known safe mappings
    if reason in _SAFE_REASONS:
        return _SAFE_REASONS[reason]
    lower = reason.lower()
    # Check specific patterns first (most → least specific)
    if "below" in lower and "threshold" in lower:
        return "Below seller threshold"
    if "exceeds budget" in lower:
        return "Exceeds budget"
    # Catch-all for reasons with sensitive numerical context
    if any(keyword in lower for keyword in (
        "valuation", "reservation", "threshold", "surplus",
    )):
        return "No deal"
    # Unknown reason — strip to avoid leaking anything unexpected
    return "Negotiation concluded"


def _strip_sensitive_fields(result_dict: dict[str, Any]) -> dict[str, Any]:
    """Strip sensitive negotiation internals before sending to the parent.

    Only outcome, final_price, and reason (sanitized) leave the enclave.
    """
    safe = {k: v for k, v in result_dict.items() if k in _SAFE_RESULT_FIELDS}
    if "reason" in safe:
        safe["reason"] = _sanitize_reason(safe["reason"])
    return safe


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
    elif action == "deliver_key":
        return _handle_deliver_key(request)
    elif action == "ping":
        return {"status": "ok", "action": "pong"}
    elif action == "vuln_negotiate":
        return _handle_vuln_negotiate(request)
    elif action == "vuln_verify":
        return _handle_vuln_verify(request)
    elif action == "deliver_overlay":
        return _handle_deliver_overlay(request)
    elif action and action.startswith("poker_"):
        from ndai.enclave.poker.actions import handle_poker_action
        return handle_poker_action(request, _state.poker_tables)
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
    safe_dict = _strip_sensitive_fields(result_dict)
    logger.info("Negotiation complete: outcome=%s", safe_dict.get("outcome"))
    return {
        "status": "ok",
        "result": safe_dict,
    }


def _handle_vuln_negotiate(request: dict[str, Any]) -> dict[str, Any]:
    """Run a vulnerability marketplace negotiation and return the result."""
    try:
        from ndai.enclave.agents.base_agent import VulnerabilitySubmission
        from ndai.enclave.vuln_session import VulnNegotiationSession, VulnSessionConfig

        data = request.get("data", request)
        vuln_data = data.get("vulnerability", {})

        vuln = VulnerabilitySubmission(
            target_software=vuln_data["target_software"],
            target_version=vuln_data["target_version"],
            vulnerability_class=vuln_data["vulnerability_class"],
            impact_type=vuln_data["impact_type"],
            affected_component=vuln_data.get("affected_component", ""),
            cvss_self_assessed=float(vuln_data["cvss_self_assessed"]),
            discovery_date=vuln_data["discovery_date"],
            patch_status=vuln_data.get("patch_status", "unpatched"),
            exclusivity=vuln_data.get("exclusivity", "exclusive"),
            outside_option_value=float(vuln_data.get("outside_option_value", 0.3)),
            max_disclosure_level=int(vuln_data.get("max_disclosure_level", 3)),
            embargo_days=int(vuln_data.get("embargo_days", 90)),
            software_category=vuln_data.get("software_category", "default"),
        )

        config = VulnSessionConfig(
            vulnerability=vuln,
            budget_cap=float(data.get("budget_cap", 1.0)),
            max_rounds=int(data.get("max_rounds", 5)),
            llm_provider=data.get("llm_provider", "openai"),
            api_key=_state.api_key or data.get("api_key", ""),
            llm_model=data.get("llm_model", "gpt-4o"),
            software_category=vuln_data.get("software_category", "default"),
        )

        session = VulnNegotiationSession(config)
        result = session.run()

        # Only safe fields leave the enclave
        safe_result = {
            "outcome": result.outcome.value,
            "final_price": result.final_price,
            "reason": result.reason,
        }

        return {"status": "ok", "result": safe_result}

    except (KeyError, ValueError, TypeError) as exc:
        logger.error("Invalid vuln negotiation request: %s", exc)
        return {"status": "error", "error": f"Invalid request: {exc}"}
    except Exception:
        logger.exception("Vuln negotiation failed")
        return {"status": "error", "error": "Negotiation failed. Check enclave logs."}


def _handle_vuln_verify(request: dict[str, Any]) -> dict[str, Any]:
    """Run PoC verification against the target software in this enclave."""
    try:
        from ndai.enclave.vuln_verify.models import (
            ConfigFile, ExpectedOutcome, PinnedPackage, PoCSpec, ServiceSpec, TargetSpec,
        )
        from ndai.enclave.vuln_verify.overlay_handler import OverlayHandler
        from ndai.enclave.vuln_verify.protocol import VulnVerificationProtocol
        from ndai.enclave.vuln_verify.security import validate_target_spec

        data = request.get("data", request)
        spec_data = data.get("target_spec", {})

        spec = TargetSpec(
            spec_id=spec_data.get("spec_id", ""),
            base_image=spec_data.get("base_image", ""),
            packages=[PinnedPackage(**p) for p in spec_data.get("packages", [])],
            config_files=[ConfigFile(**c) for c in spec_data.get("config_files", [])],
            services=[ServiceSpec(**s) for s in spec_data.get("services", [])],
            poc=PoCSpec(**spec_data.get("poc", {"script_type": "bash", "script_content": "true"})),
            expected_outcome=ExpectedOutcome(**spec_data.get("expected_outcome", {})),
        )

        # Validate inside the enclave (defense in depth — parent already validated)
        errors = validate_target_spec(spec)
        if errors:
            return {"status": "error", "error": f"Target spec validation failed: {len(errors)} error(s)"}

        overlay = _state.pending_overlay
        overlay_handler = OverlayHandler(keypair=_state.keypair) if overlay else None

        protocol = VulnVerificationProtocol(
            spec=spec, overlay=overlay, overlay_handler=overlay_handler,
        )
        result = protocol.run()

        # Clear overlay after use
        _state.pending_overlay = None

        # Only safe fields leave the enclave
        safe_result = {
            "spec_id": result.spec_id,
            "unpatched_matches": result.unpatched_matches_expected,
            "patched_matches": result.patched_matches_expected,
            "overlap_detected": result.overlap_detected,
            "verification_chain_hash": result.verification_chain_hash,
            "timestamp": result.timestamp,
        }

        return {"status": "ok", "result": safe_result}

    except (KeyError, ValueError, TypeError) as exc:
        logger.error("Invalid vuln verify request: %s", exc)
        return {"status": "error", "error": f"Invalid request: {exc}"}
    except Exception:
        logger.exception("Vuln verification failed")
        return {"status": "error", "error": "Verification failed. Check enclave logs."}


def _handle_deliver_overlay(request: dict[str, Any]) -> dict[str, Any]:
    """Receive and decrypt a buyer's overlay."""
    try:
        from ndai.enclave.vuln_verify.overlay_handler import OverlayHandler

        encrypted_data = request.get("encrypted_overlay")
        if not encrypted_data:
            return {"status": "error", "error": "No encrypted_overlay in request"}

        if isinstance(encrypted_data, str):
            import base64
            encrypted_bytes = base64.b64decode(encrypted_data)
        else:
            encrypted_bytes = bytes(encrypted_data)

        handler = OverlayHandler(keypair=_state.keypair)
        _state.pending_overlay = handler.decrypt_overlay(encrypted_bytes)

        logger.info(
            "Overlay delivered: %d file replacements",
            len(_state.pending_overlay.file_replacements),
        )
        return {"status": "ok", "files": len(_state.pending_overlay.file_replacements)}

    except Exception as exc:
        logger.error("Overlay delivery failed: %s", exc)
        return {"status": "error", "error": "Overlay delivery failed. Check enclave logs."}


def _handle_attestation(request: dict[str, Any]) -> dict[str, Any]:
    """Generate an attestation document.

    Uses the real Nitro Security Module (/dev/nsm) when available.
    Falls back to NSMStub for development.

    The ephemeral public key is embedded in the attestation document
    so the parent can encrypt the API key for secure delivery.
    """
    nonce_hex = request.get("nonce")
    nonce = bytes.fromhex(nonce_hex) if nonce_hex else None

    # Get the public key to embed in attestation
    public_key_der = None
    if _state.keypair:
        public_key_der = _state.keypair.public_key_der

    if _state.nitro_mode:
        return _handle_attestation_nsm(nonce, public_key_der)
    else:
        return _handle_attestation_stub(nonce, public_key_der)


def _handle_attestation_nsm(
    nonce: bytes | None,
    public_key_der: bytes | None,
) -> dict[str, Any]:
    """Generate attestation using the real NSM device."""
    try:
        from ndai.enclave.nsm import NSMDevice

        with NSMDevice() as nsm:
            attestation_doc = nsm.get_attestation(
                public_key=public_key_der,
                nonce=nonce,
            )

        import base64
        return {
            "status": "ok",
            "attestation_doc": base64.b64encode(attestation_doc).decode("ascii"),
            "format": "cose_sign1",
        }
    except Exception as exc:
        logger.error("NSM attestation failed: %s", exc)
        return {
            "status": "error",
            "error": f"NSM attestation failed: {exc}",
        }


def _handle_attestation_stub(
    nonce: bytes | None,
    public_key_der: bytes | None,
) -> dict[str, Any]:
    """Generate attestation using the NSMStub (development mode)."""
    try:
        from ndai.enclave.nsm_stub import NSMStub

        # Cache the stub so consecutive attestation requests use the same signing key
        if _state.nsm_stub is None:
            _state.nsm_stub = NSMStub()
        stub = _state.nsm_stub
        attestation_doc = stub.get_attestation(
            public_key=public_key_der,
            nonce=nonce,
        )

        import base64
        return {
            "status": "ok",
            "attestation_doc": base64.b64encode(attestation_doc).decode("ascii"),
            "format": "cose_sign1",
        }
    except Exception as exc:
        logger.error("Stub attestation failed: %s", exc)
        # Fall back to legacy stub format for backwards compatibility
        logger.warning("Falling back to legacy stub attestation")
        return {
            "status": "ok",
            "attestation": "stub_attestation_no_nsm",
            "nonce": nonce.hex() if nonce else None,
        }


def _handle_deliver_key(request: dict[str, Any]) -> dict[str, Any]:
    """Receive and decrypt an API key encrypted to our ephemeral public key.

    Expected request:
    {
        "action": "deliver_key",
        "encrypted_key": "<base64-encoded ECIES ciphertext>"
    }
    """
    if _state.keypair is None:
        return {
            "status": "error",
            "error": "No keypair available — enclave not initialized",
        }

    encrypted_b64 = request.get("encrypted_key")
    if not encrypted_b64:
        return {
            "status": "error",
            "error": "Missing encrypted_key field",
        }

    try:
        import base64
        from ndai.enclave.ephemeral_keys import decrypt_api_key

        encrypted_payload = base64.b64decode(encrypted_b64)
        _state.api_key = decrypt_api_key(
            _state.keypair.private_key,
            encrypted_payload,
        )

        # Log success without revealing any part of the key
        logger.info("API key delivered successfully (%d chars)", len(_state.api_key))
        return {"status": "ok"}

    except Exception as exc:
        logger.error("Failed to decrypt API key: %s", exc)
        return {
            "status": "error",
            "error": f"Key delivery failed: {exc}",
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
    # Initialize enclave state (keypair generation)
    _state.initialize()

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
