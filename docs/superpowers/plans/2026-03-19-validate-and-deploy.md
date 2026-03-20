# Validate & Deploy: CDP Wet Test, Base Sepolia Deploy, Full Flow Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate the CDP browser tunnel works with real Chrome, deploy the escrow factory to Base Sepolia, and prove the full fund→negotiate→settle→release cycle works end-to-end.

**Architecture:** Three sequential validation phases: (1) CDP tunnel integration test using neko-chrome Docker sidecar in simulated mode, (2) Foundry deploy script to Base Sepolia with recorded factory address, (3) full-loop integration test on Anvil local chain combining escrow + simulated TEE + browser tools.

**Tech Stack:** Docker (neko-chrome), pytest-asyncio, Foundry (forge script, anvil), web3.py, websockets

**Prerequisite bug fix:** The Python `EscrowClient.create_deal()` passes a `buyer_address` argument to `createEscrow()` which the Solidity factory doesn't accept (factory uses `msg.sender` as buyer). Must be fixed before integration tests.

---

## Task 1: Fix EscrowClient.create_deal Signature

**Files:**
- Modify: `ndai/blockchain/escrow_client.py:127-158`
- Modify: `tests/unit/test_escrow_client.py`

- [ ] **Step 1: Write a test that exercises the function signature**

Add to `tests/unit/test_escrow_client.py`:
```python
class TestCreateDealSignature:
    def test_create_deal_does_not_accept_buyer_address(self):
        """create_deal should match factory's createEscrow(seller, operator, reservePrice, deadline)."""
        import inspect
        from ndai.blockchain.escrow_client import EscrowClient
        sig = inspect.signature(EscrowClient.create_deal)
        param_names = list(sig.parameters.keys())
        assert "buyer_address" not in param_names
        assert "seller_address" in param_names
        assert "operator_address" in param_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_escrow_client.py::TestCreateDealSignature -v`
Expected: FAIL (buyer_address is currently a parameter)

- [ ] **Step 3: Fix create_deal**

In `ndai/blockchain/escrow_client.py`, change `create_deal` to remove `buyer_address` and pass only the 4 args the factory expects:

```python
    async def create_deal(
        self,
        seller_address: str,
        operator_address: str,
        reserve_price_wei: int,
        deadline: int,
        budget_cap_wei: int,
        private_key: str,
    ) -> str:
        """Deploy a new NdaiEscrow via the factory.

        The buyer is msg.sender (derived from private_key).
        """
        seller = AsyncWeb3.to_checksum_address(seller_address)
        operator = AsyncWeb3.to_checksum_address(operator_address)

        fn = self._factory.functions.createEscrow(
            seller, operator, reserve_price_wei, deadline
        )
        return await self._send_tx(fn, private_key, value_wei=budget_cap_wei)
```

- [ ] **Step 4: Fix any callers**

Search for `create_deal` calls in `ndai/api/routers/negotiations.py` and update if needed (currently no callers — the buyer funding flow isn't wired to an endpoint yet, only the `submit_outcome` post-negotiation path is).

- [ ] **Step 5: Run all tests**

Run: `pytest tests/unit/test_escrow_client.py -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add ndai/blockchain/escrow_client.py tests/unit/test_escrow_client.py
git commit -m "fix: remove buyer_address from create_deal to match factory signature"
```

---

## Task 2: CDP Browser Tunnel Integration Test

**Files:**
- Create: `tests/integration/test_browser_integration.py`

**Requires:** Docker running, neko-chrome container up on port 9222. If not available, test skips.

- [ ] **Step 1: Start neko-chrome**

```bash
cd /Users/discordwell/Projects/ndai-hackathon/deploy
docker compose up -d neko
# Wait for health check
sleep 15
curl -s http://localhost:9222/json/version | head -1
```

Expected: JSON response with `"Browser": "Google Chrome/..."` (or skip if Docker not available)

- [ ] **Step 2: Write the integration test**

Write `tests/integration/test_browser_integration.py`:
```python
"""Integration test: CDP tunnel client → real Chrome via neko-chrome.

Requires: docker compose up neko (port 9222)
Skipped automatically if Chrome is not reachable.
"""

import pytest
import httpx

from ndai.enclave.tunnel_cdp_client import TunnelCdpClient
from ndai.enclave.agents.browser_tools import BrowserTools

CHROME_URL = "ws://localhost:9222"
CHROME_HTTP = "http://localhost:9222"


@pytest.fixture(scope="module")
def chrome_available():
    """Skip entire module if Chrome is not reachable."""
    try:
        r = httpx.get(f"{CHROME_HTTP}/json/version", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        pytest.skip("Chrome not available on port 9222 (run: cd deploy && docker compose up -d neko)")


@pytest.fixture
async def cdp_client(chrome_available):
    """Create a TunnelCdpClient in simulated (direct TCP) mode."""
    client = TunnelCdpClient(simulated=True, chrome_url=CHROME_URL)
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def browser(cdp_client):
    return BrowserTools(cdp_client)


class TestCdpConnection:
    @pytest.mark.asyncio
    async def test_connect_and_version(self, chrome_available):
        """Verify we can connect to Chrome and get version info."""
        assert "Browser" in chrome_available
        assert "Chrome" in chrome_available["Browser"]

    @pytest.mark.asyncio
    async def test_cdp_client_connects(self, cdp_client):
        """Verify TunnelCdpClient connects successfully."""
        assert cdp_client._ws is not None


class TestBrowserNavigation:
    @pytest.mark.asyncio
    async def test_navigate_to_example(self, browser):
        """Navigate to example.com and verify title."""
        result = await browser.navigate("https://example.com")
        assert "Example" in result.get("title", "")

    @pytest.mark.asyncio
    async def test_screenshot_returns_base64(self, browser):
        """Take a screenshot and verify it's base64 PNG data."""
        await browser.navigate("https://example.com")
        data = await browser.screenshot()
        assert len(data) > 100  # Non-trivial base64 string
        # PNG magic bytes in base64: iVBOR
        assert data.startswith("iVBOR")

    @pytest.mark.asyncio
    async def test_scrape_extracts_structure(self, browser):
        """Scrape example.com and verify structured data."""
        result = await browser.scrape("https://example.com")
        assert "title" in result
        assert "Example" in result["title"]

    @pytest.mark.asyncio
    async def test_execute_js(self, browser):
        """Execute JavaScript and get result."""
        await browser.navigate("https://example.com")
        result = await browser.execute_js("2 + 2")
        assert result == 4

    @pytest.mark.asyncio
    async def test_get_page_text(self, browser):
        """Get visible text from the page."""
        await browser.navigate("https://example.com")
        text = await browser.get_page_text()
        assert "Example Domain" in text

    @pytest.mark.asyncio
    async def test_click_link(self, browser):
        """Click a link on example.com."""
        await browser.navigate("https://example.com")
        result = await browser.click("a")
        assert result.get("success") is True


class TestBrowserInteraction:
    @pytest.mark.asyncio
    async def test_multi_page_workflow(self, browser):
        """Navigate, scrape, screenshot — multi-step workflow."""
        nav = await browser.navigate("https://httpbin.org/html")
        assert nav.get("title") is not None

        text = await browser.get_page_text()
        assert "Herman Melville" in text  # httpbin.org/html has Moby Dick excerpt

        screenshot = await browser.screenshot()
        assert len(screenshot) > 100
```

- [ ] **Step 3: Run the test**

Run: `pytest tests/integration/test_browser_integration.py -v`
Expected: All pass (or all skip if Chrome not available)

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_browser_integration.py
git commit -m "test: CDP browser tunnel integration test with real Chrome"
```

---

## Task 3: Deploy Factory to Base Sepolia

**Files:**
- Modify: `contracts/script/Deploy.s.sol` (minor — it's already correct)
- Create: `contracts/deployments/base-sepolia.json` (record deployment)

**Requires:** `BASE_SEPOLIA_RPC_URL` and a funded wallet in `.env`

- [ ] **Step 1: Set up wallet (if not done)**

```bash
export PATH="$HOME/.foundry/bin:$PATH"
cd /Users/discordwell/Projects/ndai-hackathon/contracts

# Generate a new wallet and save the address
cast wallet new

# Record the private key in .env as ESCROW_OPERATOR_KEY
# Fund the wallet with Base Sepolia ETH from a faucet
```

- [ ] **Step 2: Deploy the factory**

```bash
cd /Users/discordwell/Projects/ndai-hackathon/contracts

source ../.env

forge script script/Deploy.s.sol:Deploy \
    --rpc-url "$BASE_SEPOLIA_RPC_URL" \
    --private-key "$ESCROW_OPERATOR_KEY" \
    --broadcast \
    -v
```

Expected: Output includes `Factory deployed at: 0x...`

- [ ] **Step 3: Record the deployment**

Create `contracts/deployments/base-sepolia.json`:
```json
{
    "chain_id": 84532,
    "factory_address": "<address from step 2>",
    "deployer": "<operator address>",
    "deploy_tx": "<tx hash from step 2>",
    "deployed_at": "<ISO timestamp>",
    "forge_version": "<forge --version output>"
}
```

- [ ] **Step 4: Update .env with factory address**

Add `ESCROW_FACTORY_ADDRESS=0x...` to `.env` (matching the deployed address).

- [ ] **Step 5: Verify on BaseScan (optional)**

```bash
forge verify-contract <factory_address> src/NdaiEscrowFactory.sol:NdaiEscrowFactory \
    --chain base-sepolia \
    --etherscan-api-key "$ETHERSCAN_API_KEY"
```

- [ ] **Step 6: Commit**

```bash
git add contracts/deployments/
git commit -m "deploy: NdaiEscrowFactory on Base Sepolia"
```

---

## Task 4: Full Flow Integration Test (Anvil)

**Files:**
- Create: `tests/integration/test_full_escrow_flow.py`

**Requires:** Anvil (bundled with Foundry), Foundry compiled contracts. No external services.

- [ ] **Step 1: Write the full flow test**

Write `tests/integration/test_full_escrow_flow.py`:
```python
"""Full escrow lifecycle test on Anvil local chain.

Tests the complete flow: deploy factory → create deal → submit outcome →
accept deal → verify funds transferred.

Requires: forge build (contracts/out/ must exist)
Skipped if Anvil is not running.
"""

import asyncio
import subprocess
import time

import pytest
import httpx

from ndai.blockchain.escrow_client import EscrowClient
from ndai.blockchain.models import EscrowState

ANVIL_URL = "http://127.0.0.1:8545"

# Anvil default accounts (well-known test keys)
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEPLOYER_ADDR = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
BUYER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
BUYER_ADDR = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"
SELLER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
SELLER_ADDR = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"
OPERATOR_KEY = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
OPERATOR_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"


@pytest.fixture(scope="module")
def anvil_available():
    """Skip if Anvil is not running on port 8545."""
    try:
        r = httpx.post(
            ANVIL_URL,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=2,
        )
        r.raise_for_status()
    except Exception:
        pytest.skip("Anvil not running on port 8545 (run: anvil --port 8545)")


@pytest.fixture(scope="module")
def factory_address(anvil_available):
    """Deploy the factory to Anvil and return its address."""
    import subprocess, os
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~')}/.foundry/bin:" + env.get("PATH", "")
    result = subprocess.run(
        [
            "forge", "script", "script/Deploy.s.sol:Deploy",
            "--rpc-url", ANVIL_URL,
            "--private-key", DEPLOYER_KEY,
            "--broadcast",
        ],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2] / "contracts"),
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"Deploy failed: {result.stderr}"
    # Parse factory address from output
    for line in result.stdout.split("\n"):
        if "Factory deployed at:" in line:
            addr = line.split("Factory deployed at:")[1].strip()
            return addr
    pytest.fail(f"Could not parse factory address from output:\n{result.stdout}")


@pytest.mark.asyncio
class TestFullEscrowLifecycle:
    async def test_create_deal(self, factory_address):
        """Buyer creates and funds an escrow deal."""
        client = EscrowClient(
            rpc_url=ANVIL_URL,
            factory_address=factory_address,
            chain_id=31337,  # Anvil default
        )

        from web3 import AsyncWeb3
        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(ANVIL_URL))
        block = await w3.eth.get_block("latest")
        deadline = block["timestamp"] + 86400  # +1 day

        tx_hash = await client.create_deal(
            seller_address=SELLER_ADDR,
            operator_address=OPERATOR_ADDR,
            reserve_price_wei=int(0.1e18),
            deadline=deadline,
            budget_cap_wei=int(1e18),
            private_key=BUYER_KEY,
        )
        assert tx_hash is not None
        assert len(tx_hash) == 66  # 0x + 64 hex chars

    async def test_full_lifecycle(self, factory_address):
        """Full cycle: create → submit outcome → accept → verify balances."""
        client = EscrowClient(
            rpc_url=ANVIL_URL,
            factory_address=factory_address,
            chain_id=31337,
        )

        from web3 import AsyncWeb3
        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(ANVIL_URL))
        block = await w3.eth.get_block("latest")
        deadline = block["timestamp"] + 86400

        budget = int(1e18)  # 1 ETH
        reserve = int(0.1e18)  # 0.1 ETH
        price = int(0.5e18)  # 0.5 ETH

        # Record balances before
        seller_before = await w3.eth.get_balance(SELLER_ADDR)

        # Step 1: Buyer creates deal
        tx = await client.create_deal(
            seller_address=SELLER_ADDR,
            operator_address=OPERATOR_ADDR,
            reserve_price_wei=reserve,
            deadline=deadline,
            budget_cap_wei=budget,
            private_key=BUYER_KEY,
        )

        # Find escrow address from factory
        factory_abi_path = __import__("pathlib").Path(__file__).resolve().parents[2] / "contracts" / "out" / "NdaiEscrowFactory.sol" / "NdaiEscrowFactory.json"
        import json
        with open(factory_abi_path) as f:
            factory_abi = json.load(f)["abi"]
        factory = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(factory_address),
            abi=factory_abi,
        )
        escrows = await factory.functions.getEscrows().call()
        escrow_address = escrows[-1]

        # Verify deal state
        state = await client.get_deal_state(escrow_address)
        assert state.state == EscrowState.Funded
        assert state.budget_cap_wei == budget
        assert state.reserve_price_wei == reserve

        # Step 2: Operator submits outcome
        att_hash = EscrowClient.compute_attestation_hash(
            b"\x01" * 32, b"\x02" * 32, b"\x03" * 32
        )
        await client.submit_outcome(
            escrow_address=escrow_address,
            final_price_wei=price,
            attestation_hash=att_hash,
            private_key=OPERATOR_KEY,
        )

        state = await client.get_deal_state(escrow_address)
        assert state.state == EscrowState.Evaluated
        assert state.final_price_wei == price

        # Step 3: Seller accepts
        await client.accept_deal(
            escrow_address=escrow_address,
            private_key=SELLER_KEY,
        )

        state = await client.get_deal_state(escrow_address)
        assert state.state == EscrowState.Accepted
        assert state.balance_wei == 0  # All funds distributed

        # Verify seller received payment
        seller_after = await w3.eth.get_balance(SELLER_ADDR)
        assert seller_after == seller_before + price

    async def test_reject_lifecycle(self, factory_address):
        """Seller rejects → buyer gets full refund."""
        client = EscrowClient(
            rpc_url=ANVIL_URL,
            factory_address=factory_address,
            chain_id=31337,
        )

        from web3 import AsyncWeb3
        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(ANVIL_URL))
        block = await w3.eth.get_block("latest")
        deadline = block["timestamp"] + 86400

        budget = int(1e18)
        buyer_before = await w3.eth.get_balance(BUYER_ADDR)

        await client.create_deal(
            seller_address=SELLER_ADDR,
            operator_address=OPERATOR_ADDR,
            reserve_price_wei=int(0.1e18),
            deadline=deadline,
            budget_cap_wei=budget,
            private_key=BUYER_KEY,
        )

        factory_abi_path = __import__("pathlib").Path(__file__).resolve().parents[2] / "contracts" / "out" / "NdaiEscrowFactory.sol" / "NdaiEscrowFactory.json"
        import json
        with open(factory_abi_path) as f:
            factory_abi = json.load(f)["abi"]
        factory = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(factory_address),
            abi=factory_abi,
        )
        escrows = await factory.functions.getEscrows().call()
        escrow_address = escrows[-1]

        # Operator submits, seller rejects
        att_hash = EscrowClient.compute_attestation_hash(b"\x01" * 32, b"\x02" * 32, b"\x03" * 32)
        await client.submit_outcome(escrow_address, int(0.5e18), att_hash, OPERATOR_KEY)
        await client.reject_deal(escrow_address, SELLER_KEY)

        state = await client.get_deal_state(escrow_address)
        assert state.state == EscrowState.Rejected
        assert state.balance_wei == 0

    async def test_verify_attestation(self, factory_address):
        """Verify attestation hash matches on-chain."""
        client = EscrowClient(
            rpc_url=ANVIL_URL,
            factory_address=factory_address,
            chain_id=31337,
        )

        from web3 import AsyncWeb3
        w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(ANVIL_URL))
        block = await w3.eth.get_block("latest")
        deadline = block["timestamp"] + 86400

        await client.create_deal(
            seller_address=SELLER_ADDR,
            operator_address=OPERATOR_ADDR,
            reserve_price_wei=int(0.1e18),
            deadline=deadline,
            budget_cap_wei=int(1e18),
            private_key=BUYER_KEY,
        )

        factory_abi_path = __import__("pathlib").Path(__file__).resolve().parents[2] / "contracts" / "out" / "NdaiEscrowFactory.sol" / "NdaiEscrowFactory.json"
        import json
        with open(factory_abi_path) as f:
            factory_abi = json.load(f)["abi"]
        factory = w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(factory_address),
            abi=factory_abi,
        )
        escrows = await factory.functions.getEscrows().call()
        escrow_address = escrows[-1]

        pcr0 = b"\xAA" * 32
        nonce = b"\xBB" * 32
        outcome = b"\xCC" * 32
        att_hash = EscrowClient.compute_attestation_hash(pcr0, nonce, outcome)

        await client.submit_outcome(escrow_address, int(0.5e18), att_hash, OPERATOR_KEY)

        assert await client.verify_attestation(escrow_address, pcr0, nonce, outcome)
        assert not await client.verify_attestation(escrow_address, b"\x00" * 32, nonce, outcome)
```

- [ ] **Step 2: Start Anvil**

```bash
export PATH="$HOME/.foundry/bin:$PATH"
anvil --port 8545 &
```

- [ ] **Step 3: Build contracts (ensure ABIs exist)**

```bash
cd /Users/discordwell/Projects/ndai-hackathon/contracts
export PATH="$HOME/.foundry/bin:$PATH"
forge build
```

- [ ] **Step 4: Run the integration test**

Run: `pytest tests/integration/test_full_escrow_flow.py -v`
Expected: All 4 tests pass

- [ ] **Step 5: Stop Anvil**

```bash
kill %1  # or: pkill anvil
```

- [ ] **Step 6: Commit**

```bash
git add tests/integration/test_full_escrow_flow.py
git commit -m "test: full escrow lifecycle integration test on Anvil"
```

---

## Task 5: Final Validation — Run Everything

**Files:** None (validation only)

- [ ] **Step 1: Run all Foundry tests**

```bash
export PATH="$HOME/.foundry/bin:$PATH"
cd /Users/discordwell/Projects/ndai-hackathon/contracts
forge test --summary
```

Expected: 37 tests pass, 0 failed

- [ ] **Step 2: Run all Python unit tests**

```bash
cd /Users/discordwell/Projects/ndai-hackathon
pytest tests/unit/ -v --tb=short
```

Expected: All pass

- [ ] **Step 3: Run integration tests (with Anvil + optionally Chrome)**

```bash
# Start Anvil in background
export PATH="$HOME/.foundry/bin:$PATH"
anvil --port 8545 &
ANVIL_PID=$!

# Run integration tests
pytest tests/integration/ -v --tb=short

# Stop Anvil
kill $ANVIL_PID
```

Expected: Escrow flow tests pass. Browser tests pass if Chrome is running, skip otherwise.

- [ ] **Step 4: Push**

```bash
git push
```
