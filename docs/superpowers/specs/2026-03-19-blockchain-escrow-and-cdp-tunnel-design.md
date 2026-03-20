# Blockchain Escrow & CDP Browser Tunnel Design

**Date:** 2026-03-19
**Status:** Approved
**Context:** Bring NDAI up to par with dnai-wikigen on blockchain settlement and browser-in-TEE evaluation capabilities.

## Overview

Two independent subsystems added to the existing NDAI architecture:

1. **On-chain escrow** — A Solidity contract on Base Sepolia that locks buyer funds, enforces the paper's price constraints (reserve price, budget cap), records attestation hashes, and handles time-based expiry. Replaces the mock `Payment` model as the authoritative settlement layer.

2. **CDP browser tunnel** — A vsock-based tunnel (port 5003) that lets the enclave drive a Chrome instance on the parent via Chrome DevTools Protocol. The evaluator agent gains browser tools (navigate, screenshot, scrape, execute JS, fill forms, click) for interactive evaluation of web-based artifacts.

## 1. On-Chain Escrow Contract

### 1.1 Contract: `contracts/src/NdaiEscrow.sol`

Foundry project at `contracts/` with `foundry.toml`. One contract instance per deal, created via a factory pattern (`NdaiEscrowFactory.sol`).

**State machine:**
```
Created → Funded → Evaluated → Accepted / Rejected
                                    ↓         ↓
                              (seller paid) (buyer refunded)

Any state → Expired (after deadline, buyer auto-refunded)
```

**Storage:**
- `seller` / `buyer` — addresses
- `operator` — address (the orchestrator, authorized to call `submitOutcome`)
- `reservePrice` — seller's minimum (wei)
- `budgetCap` — `msg.value` sent by buyer during creation (wei). This is the maximum the buyer is willing to pay; it equals the amount of ETH locked in the contract.
- `finalPrice` — set by orchestrator after enclave negotiation (wei)
- `attestationHash` — `keccak256(abi.encodePacked(pcr0, nonce, outcome))` proving result origin
- `deadline` — `block.timestamp` after which buyer can reclaim
- `state` — enum: Created, Funded, Evaluated, Accepted, Rejected, Expired

**Contract creation flow:** The factory handles deployment and funding in a single transaction. The buyer calls:

```solidity
factory.createEscrow{value: budgetCap}(seller, operator, reservePrice, deadline)
```

This deploys a new `NdaiEscrow` and forwards `msg.value` to it. The escrow's `budgetCap` is set to the forwarded ETH amount. The contract starts in state `Funded` (Created is skipped since funding is atomic with creation).

**Functions:**
- `submitOutcome(finalPrice, attestationHash)` — `operator` only. Enforces `finalPrice <= budgetCap && finalPrice >= reservePrice`. Sets state to Evaluated.
- `acceptDeal()` — `seller` only (`msg.sender == seller`). Transfers `finalPrice` to seller, remainder to buyer. Uses Checks-Effects-Interactions pattern + OpenZeppelin `ReentrancyGuard`. State → Accepted.
- `rejectDeal()` — `seller` only. Refunds buyer entirely. State → Rejected.
- `claimExpired()` — anyone calls after `deadline`. Refunds buyer. State → Expired.
- `verifyAttestation(pcr0, nonce, outcome) → bool` — view function, recomputes hash and checks against stored `attestationHash`.

**Events:** `DealCreated`, `OutcomeSubmitted`, `DealAccepted`, `DealRejected`, `DealExpired` — each with indexed escrow address and relevant parameters.

**Factory: `NdaiEscrowFactory.sol`**
- `createEscrow{value}(seller, operator, reservePrice, deadline) → address` — deploys and funds a new `NdaiEscrow` in one tx, returns its address
- Maintains a registry of all escrow addresses for enumeration
- Emits `EscrowCreated(address indexed escrow, address indexed buyer, address indexed seller)`

### 1.2 Python Escrow Client: `ndai/blockchain/escrow_client.py`

Async wrapper using `web3.py` (AsyncHTTPProvider).

**Class: `EscrowClient`**
- Constructor: `rpc_url`, `factory_address`, `chain_id`
- Each method that sends a tx takes an optional `private_key` parameter, allowing different wallets per role

**Wallet model — three distinct roles, three distinct keys:**
- **Buyer wallet** — calls `create_deal()` and sends ETH. This is the buyer's own key (provided at deal creation time, not stored server-side).
- **Operator wallet** (`escrow_operator_key` in config) — the orchestrator's key, used to call `submit_outcome()`. This is the only key the server holds permanently.
- **Seller wallet** — calls `accept_deal()` / `reject_deal()`. This is the seller's own key. In the MVP, the API accepts the seller's signed transaction from the frontend (MetaMask-style). Alternatively, the seller can delegate to the operator via a `seller_delegate` flag on the contract.

**Methods:**
- `create_deal(seller_address, reserve_price_wei, budget_cap_wei, deadline_seconds, buyer_private_key) → (tx_hash, escrow_address)` — calls factory, sends buyer's ETH
- `submit_outcome(escrow_address, final_price_wei, attestation_hash, operator_private_key) → tx_hash`
- `accept_deal(escrow_address, seller_private_key) → tx_hash`
- `reject_deal(escrow_address, seller_private_key) → tx_hash`
- `claim_expired(escrow_address, any_private_key) → tx_hash`
- `get_deal_state(escrow_address) → DealState` dataclass (read-only, no key needed)
- `verify_attestation(escrow_address, pcr0, nonce, outcome) → bool` (read-only)

**Config additions (`ndai/config.py`):**
```python
base_sepolia_rpc_url: str = ""
escrow_factory_address: str = ""
escrow_operator_key: str = ""  # Orchestrator's wallet only
chain_id: int = 84532  # Base Sepolia
blockchain_enabled: bool = False  # Feature flag for gradual rollout
```

### 1.3 Orchestrator Integration

The negotiation flow in `ndai/api/routers/negotiations.py` gains pre- and post-negotiation blockchain steps:

1. **Pre-negotiation:** Buyer funds deal via `EscrowClient.create_deal()`. Escrow address stored on `Agreement.escrow_address` (new column).
2. **Negotiation:** Existing enclave flow (unchanged).
3. **Post-negotiation:** Orchestrator calls `EscrowClient.submit_outcome()` with `final_price` and `attestation_hash`.
4. **Settlement:** Seller accepts/rejects via API endpoint that forwards a signed transaction, or signs server-side if seller has delegated.

**Attestation hash computation:** The orchestrator computes the attestation hash after the enclave returns a result. The `_run_nitro` method already has the attestation result (with PCR values and nonce). The hash is:

```python
attestation_hash = keccak256(abi.encodePacked(
    attestation.pcrs[0],   # PCR0 — enclave image hash
    nonce,                  # 32-byte random nonce used for attestation
    outcome_bytes           # keccak256 of JSON-serialized NegotiationResult
))
```

To propagate this, `run_negotiation()` returns a new `NegotiationOutcomeWithAttestation` dataclass:

```python
@dataclass
class NegotiationOutcomeWithAttestation:
    result: NegotiationResult
    attestation_hash: bytes  # 32-byte keccak256
    pcr0: str
    nonce: bytes
```

When `blockchain_enabled` is `False`, the existing `NegotiationResult` return path is used (no breaking change).

**Relationship to `Payment` model:** The `Payment` table stays as a local audit trail. After each on-chain tx, a `Payment` row is written with the tx hash in `transaction_hash` (renamed from `mock_transaction_id`). The contract is authoritative; the DB is a read cache.

**Blockchain unavailability:** If `blockchain_enabled` is `True` but the RPC endpoint is unreachable, the negotiation endpoint returns a 503 error before launching the enclave. Negotiations do not proceed without confirmed escrow funding. This is fail-fast by design — partial settlement is worse than no settlement.

### 1.4 Agreement Model Changes

Add to `Agreement`:
- `escrow_address: str | None` — deployed escrow contract address
- `escrow_tx_hash: str | None` — creation transaction hash

Rename in `Payment`:
- `mock_transaction_id` → `transaction_hash`

**Alembic migration required.** The `mock_transaction_id` rename must use `ALTER COLUMN ... RENAME TO` (not drop+create) to preserve existing data. New columns are nullable so they are backward-compatible.

## 2. CDP Browser Tunnel

### 2.1 Architecture

```
Nitro Enclave (CID N)                  Parent EC2 Instance
┌──────────────────────────┐          ┌──────────────────────────────┐
│  Evaluator Agent         │          │                              │
│  ├── browser_tools.py    │          │  CdpTunnel                   │
│  │   (navigate, click,   │  vsock   │  (vsock port 5003            │
│  │    screenshot, etc.)  │◄────────►│   ↔ WebSocket to Chrome)     │
│  │                       │  5003    │                              │
│  └── tunnel_cdp_client   │          │  neko-chrome container       │
│      (local WS server    │          │  ├── Chrome (:9222 CDP)      │
│       ↔ vsock bridge)    │          │  └── nginx proxy             │
└──────────────────────────┘          └──────────────────────────────┘
```

### 2.2 Security Considerations

**Chrome runs outside the trust boundary.** The parent EC2 operator could:
- Serve fake web pages to the Chrome instance, deceiving the evaluator agent
- Intercept/modify CDP traffic between the enclave and Chrome (CDP is plaintext JSON, unlike the TLS-protected LLM tunnel)
- Tamper with screenshots or page content before it reaches the evaluator

**What browser tools provide:** Convenience for evaluating web-based artifacts (live web apps, dashboards, authenticated pages). The agent can interactively explore, which is impossible with static artifact delivery.

**What browser tools do NOT provide:** Cryptographic proof that the web content is authentic. A compromised parent could feed fabricated content.

**Mitigations:**
- **TLS certificate verification:** The enclave can request the page's TLS certificate chain via CDP's `Security.enable` domain and verify it against known CAs. This proves the Chrome instance is actually connecting to the claimed origin, not a parent-controlled fake — assuming the parent hasn't compromised Chrome's TLS stack.
- **Content hashing:** All browser tool responses are hashed into the transcript chain (existing `ndai/enclave/transcript.py`), creating a tamper-evident record of what the agent saw.
- **Documentation:** The attestation verification page will clearly note that browser-evaluated artifacts have a weaker trust guarantee than directly-uploaded artifacts (which are encrypted to the enclave's ephemeral key and never touch the parent).

### 2.3 Parent Side: `ndai/enclave/cdp_tunnel.py`

**Class: `CdpTunnel`**

Bridges vsock ↔ WebSocket. Same lifecycle pattern as `VsockTunnel` (raw byte forwarding).

- Constructor: `chrome_cdp_url` (default `ws://localhost:9222`), `vsock_port` (default 5003)
- `run_background()` — starts listening on vsock, on connection opens WS to Chrome's CDP endpoint
- `stop()` — closes both connections

**Protocol:** Raw byte forwarding over vsock, identical to how `VsockTunnel` (port 5002) bridges vsock to TCP. The CDP tunnel bridges vsock bytes to a WebSocket connection:

- **Enclave → Parent:** Raw bytes arrive on vsock, forwarded as WebSocket messages to Chrome
- **Chrome → Parent → Enclave:** WebSocket messages from Chrome, forwarded as raw bytes on vsock

This is NOT length-prefixed framing. It is the same CONNECT-style raw pipe as the TCP tunnel.

**HTTP endpoint proxy:** CDP's `connect_over_cdp()` first makes an HTTP GET to `/json/version` to discover the browser's WebSocket debugger URL. The `CdpTunnel` also proxies HTTP requests: when it detects an HTTP request (vs WebSocket upgrade), it forwards to Chrome's HTTP endpoint at `http://localhost:9222/json/version` and returns the response. This is a simple request-response before the WebSocket connection is established.

### 2.4 Enclave Side: `ndai/enclave/tunnel_cdp_client.py`

**Class: `TunnelCdpClient`**

Bridges the enclave's localhost to vsock for CDP traffic. Does NOT use Playwright.

Instead of Playwright (which is heavy and requires a Chromium binary even for remote connections), the enclave uses a **lightweight CDP client built on the `websockets` library**. This avoids adding ~100MB+ to the enclave image and keeps PCR impact minimal.

**Architecture:**
1. `TunnelCdpClient` opens a vsock connection to the parent's port 5003
2. Sends an HTTP GET `/json/version` to discover the browser WS URL
3. Upgrades to WebSocket and speaks CDP protocol directly
4. Exposes high-level methods that `browser_tools.py` calls

**Methods:**
- `connect()` — establish vsock → HTTP discovery → WebSocket upgrade
- `send_command(method, params) → result` — send CDP command, await response (matched by message ID)
- `close()` — tear down connection

**Why not Playwright:** Playwright's `connect_over_cdp()` requires (a) a TCP/WebSocket connection to a localhost URL, which doesn't exist in Nitro (only vsock), (b) a Chromium binary installed even when connecting remotely, and (c) ~100MB+ added to the enclave image, significantly impacting EIF build time, memory allocation, and PCR values. A raw CDP client over `websockets` (~50KB) achieves the same result with none of these costs.

**Simulated mode:** In simulated mode (no vsock), `TunnelCdpClient` connects directly via TCP WebSocket to `ws://localhost:9222`. The same CDP client code works — only the transport layer changes (TCP socket vs vsock).

### 2.5 Browser Tools: `ndai/enclave/agents/browser_tools.py`

Tool definitions for Claude/OpenAI tool-use, available to evaluator agents:

| Tool | Parameters | Returns |
|------|-----------|---------|
| `navigate` | `url: str` | `{title, status_code, url}` |
| `screenshot` | `url: str?` | base64 PNG |
| `scrape` | `url: str?` | `{title, description, headings, links}` |
| `execute_js` | `script: str` | JSON result |
| `fill_form` | `fields: dict, submit_selector: str` | `{result_title}` |
| `click` | `selector: str` | `{success: bool}` |
| `get_page_text` | — | visible text content |

Tools wrap `TunnelCdpClient`, translating high-level operations into CDP protocol commands:
- `navigate` → `Page.navigate` + `Page.loadEventFired`
- `screenshot` → `Page.captureScreenshot`
- `scrape` → `Runtime.evaluate` with DOM extraction JS
- `execute_js` → `Runtime.evaluate`
- `fill_form` → `Runtime.evaluate` to set values + `DOM.querySelector` + `Input.dispatchMouseEvent`
- `click` → `DOM.querySelector` + `Input.dispatchMouseEvent`
- `get_page_text` → `Runtime.evaluate` with `document.body.innerText`

**Credential delivery:** If the seller's artifact requires authentication, credentials are ECIES-encrypted to the enclave's ephemeral key and delivered via a new `deliver_browser_creds` vsock message. Message format:

```json
{
    "action": "deliver_browser_creds",
    "encrypted_creds": "<base64 ECIES ciphertext>"
}
```

Decrypted payload:
```json
{
    "login_url": "https://example.com/login",
    "fields": {"#username": "user", "#password": "pass"},
    "submit_selector": "#login-btn"
}
```

The enclave uses `fill_form` to authenticate after decryption.

### 2.6 Orchestrator Changes

**`EnclaveNegotiationConfig` additions:**
```python
browser_enabled: bool = False
browser_credentials: dict | None = None  # {login_url, fields, submit_selector}
target_urls: list[str] | None = None
```

**`EnclaveOrchestrator._run_nitro()` additions:**
- After step 2 (TCP tunnel), if `browser_enabled`: start `CdpTunnel` on port 5003
- After step 5 (API key delivery), if `browser_credentials`: deliver them via `deliver_browser_creds` message (ECIES-encrypted to enclave pubkey, same as API key delivery)
- Cleanup: stop CDP tunnel in `finally` block alongside TCP tunnel

**`EnclaveOrchestrator._run_simulated()` additions:**
- If `browser_enabled`: create a `TunnelCdpClient` in TCP mode (connects directly to `ws://localhost:9222`) and pass it to the `NegotiationSession`. The session makes browser tools available to agents when a CDP client is provided.

**`NegotiationSession` changes:**
- Constructor gains optional `cdp_client: TunnelCdpClient | None = None`
- When `cdp_client` is not None, browser tools are added to both agents' tool lists
- When `cdp_client` is None, browser tools are not available (existing behavior preserved)

### 2.7 Chrome Sidecar

**`deploy/docker-compose.yml` addition:**
```yaml
neko:
  build: ./deploy/neko-chrome
  shm_size: 2gb
  cap_add: [SYS_ADMIN]
  ports:
    - "9222:9222"   # CDP (note: dnai-wikigen uses 9322:9222)
    - "52100:8080"  # Neko web UI (dev only)
```

The `deploy/neko-chrome/` directory contains the Dockerfile, nginx CDP proxy config, supervisord config, and Chrome preferences — adapted from dnai-wikigen's `⚙️/cdp-playground/neko-chrome/`.

### 2.8 Enclave Image Impact

The CDP client adds only the `websockets` Python package (~50KB) to the enclave image, NOT Playwright or Chromium. Impact:
- **Image size:** Negligible increase (~50KB)
- **Memory:** No change to `enclave_memory_mib` (1600 is sufficient)
- **PCR values:** Will change (any dependency change does). New PCR0/1/2 must be recorded after rebuild.
- **Build time:** No meaningful increase

## 3. Testing

### 3.1 Escrow Tests

**Foundry (`contracts/test/`):**
- `NdaiEscrow.t.sol` — all state transitions, access control, price constraint enforcement (`finalPrice <= budgetCap`, `finalPrice >= reservePrice`), expiry, reentrancy (OpenZeppelin ReentrancyGuard), fuzz tests on price values
- `NdaiEscrowFactory.t.sol` — factory creation, registry, atomic deploy+fund

**Python (`tests/`):**
- `tests/unit/test_escrow_client.py` — `EscrowClient` against Anvil local chain (fork or clean)
- `tests/integration/test_escrow_flow.py` — full cycle: create deal → fund → negotiate (simulated) → submit outcome → accept → verify on-chain state

### 3.2 CDP Tunnel Tests

- `tests/unit/test_cdp_tunnel.py` — raw byte forwarding correctness, HTTP `/json/version` proxy, WebSocket lifecycle, error handling
- `tests/unit/test_tunnel_cdp_client.py` — CDP command send/receive, message ID matching, connection lifecycle
- `tests/unit/test_browser_tools.py` — tool definitions, parameter validation, CDP command translation
- `tests/integration/test_browser_evaluation.py` — agent uses browser tools to evaluate a test HTTP server (started in fixture), with neko-chrome running in Docker

### 3.3 Existing Tests

All existing tests must continue to pass. The `blockchain_enabled` and `browser_enabled` flags default to `False`, so existing flows are unaffected unless explicitly opted in.

## 4. Dependencies

**New Python packages:**
- `web3` — Ethereum interaction
- `websockets` — CDP client inside enclave (lightweight, ~50KB)

**New toolchain:**
- Foundry (`forge`, `cast`, `anvil`) — Solidity development

**New Docker images:**
- neko-chrome sidecar (adapted from dnai-wikigen)

## 5. File Map

```
contracts/                          # NEW — Foundry project
├── foundry.toml
├── src/
│   ├── NdaiEscrow.sol
│   └── NdaiEscrowFactory.sol
├── test/
│   ├── NdaiEscrow.t.sol
│   └── NdaiEscrowFactory.t.sol
└── script/
    └── Deploy.s.sol

ndai/blockchain/                    # NEW
├── __init__.py
├── escrow_client.py
└── models.py                       # DealState dataclass

ndai/enclave/cdp_tunnel.py          # NEW — parent-side vsock↔WS bridge
ndai/enclave/tunnel_cdp_client.py   # NEW — enclave-side lightweight CDP client
ndai/enclave/agents/browser_tools.py # NEW — agent tool definitions

deploy/neko-chrome/                 # NEW — adapted from dnai-wikigen
├── Dockerfile
├── supervisord.conf
├── nginx-cdp.conf
├── preferences.json
└── policies.json

ndai/config.py                      # MODIFIED — add blockchain + CDP settings
ndai/tee/orchestrator.py            # MODIFIED — CDP tunnel + escrow integration
ndai/enclave/session.py             # MODIFIED — accept optional cdp_client
ndai/models/agreement.py            # MODIFIED — add escrow_address column
ndai/models/payment.py              # MODIFIED — rename mock_transaction_id
ndai/api/routers/negotiations.py    # MODIFIED — pre/post negotiation blockchain steps
deploy/docker-compose.yml           # MODIFIED — add neko service
alembic/versions/                   # NEW migration for model changes
```
