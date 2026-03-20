"""Full escrow lifecycle integration tests against a local Anvil node.

Requires Anvil running on 127.0.0.1:8545 and the NdaiEscrowFactory deployed.
Tests are skipped automatically when Anvil is not available.

Run:
    anvil --port 8545 &
    forge script contracts/script/Deploy.s.sol:Deploy \\
        --rpc-url http://127.0.0.1:8545 \\
        --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \\
        --broadcast
    pytest tests/integration/test_full_escrow_flow.py -v
"""

import asyncio
import time

import pytest
import requests
from eth_account import Account
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from ndai.blockchain.escrow_client import EscrowClient
from ndai.blockchain.models import EscrowState

# ---------------------------------------------------------------------------
# Anvil default test accounts
# ---------------------------------------------------------------------------
ANVIL_RPC = "http://127.0.0.1:8545"
CHAIN_ID = 31337

# Account 0 — deployer (used to deploy factory via forge script)
DEPLOYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

# Account 1 — buyer
BUYER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
BUYER_ADDR = Account.from_key(BUYER_KEY).address  # 0x70997970C51812dc3A010C7d01b50e0d17dc79C8

# Account 2 — seller
SELLER_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"
SELLER_ADDR = "0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC"

# Account 4 — operator
OPERATOR_KEY = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"
OPERATOR_ADDR = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"

# Deal parameters
RESERVE_PRICE_WEI = int(0.01 * 1e18)   # 0.01 ETH
BUDGET_CAP_WEI    = int(0.1  * 1e18)   # 0.10 ETH — funds sent with createEscrow
FINAL_PRICE_WEI   = int(0.05 * 1e18)   # 0.05 ETH — agreed price


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def anvil_running():
    """Skip the entire module when Anvil is not reachable."""
    try:
        resp = requests.post(
            ANVIL_RPC,
            json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1},
            timeout=2,
        )
        resp.raise_for_status()
    except Exception:
        pytest.skip("Anvil not running on 127.0.0.1:8545 — skipping blockchain integration tests")


@pytest.fixture(scope="module")
def factory_address(anvil_running):
    """Deploy NdaiEscrowFactory and return its address.

    Uses a raw web3 call via a sync helper so we can run it at module scope
    without needing a running event loop fixture.
    """
    import json
    from pathlib import Path
    from eth_account import Account as _Account

    w3 = AsyncWeb3(AsyncHTTPProvider(ANVIL_RPC))

    artifact_path = (
        Path(__file__).resolve().parents[2]
        / "contracts" / "out" / "NdaiEscrowFactory.sol" / "NdaiEscrowFactory.json"
    )
    with artifact_path.open() as f:
        artifact = json.load(f)
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]["object"]

    async def _deploy():
        deployer = _Account.from_key(DEPLOYER_KEY)
        contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        nonce = await w3.eth.get_transaction_count(deployer.address)
        gas_price = await w3.eth.gas_price
        tx = await contract.constructor().build_transaction({
            "chainId": CHAIN_ID,
            "from": deployer.address,
            "nonce": nonce,
            "gasPrice": gas_price,
        })
        gas = await w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas * 1.2)
        signed = deployer.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt.contractAddress

    addr = asyncio.get_event_loop().run_until_complete(_deploy())
    return addr


@pytest.fixture(scope="module")
def client(factory_address):
    """Return a shared EscrowClient pointed at the deployed factory."""
    return EscrowClient(
        rpc_url=ANVIL_RPC,
        factory_address=factory_address,
        chain_id=CHAIN_ID,
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _get_latest_escrow(client: EscrowClient) -> str:
    """Return the most-recently created escrow address from the factory."""
    escrows = await client._factory.functions.getEscrows().call()
    assert escrows, "No escrows found in factory"
    return escrows[-1]


def _deadline_future(seconds: int = 3600) -> int:
    """Return a Unix timestamp `seconds` from now."""
    return int(time.time()) + seconds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_deal(client):
    """Buyer creates and funds an escrow; verify a tx hash is returned."""
    tx_hash = await client.create_deal(
        seller_address=SELLER_ADDR,
        operator_address=OPERATOR_ADDR,
        reserve_price_wei=RESERVE_PRICE_WEI,
        deadline=_deadline_future(),
        budget_cap_wei=BUDGET_CAP_WEI,
        private_key=BUYER_KEY,
    )

    assert isinstance(tx_hash, str)
    # EscrowClient returns raw hex (no 0x prefix) from bytes.hex()
    clean = tx_hash.lstrip("0x")
    assert len(clean) == 64, f"Expected 32-byte hex tx hash, got: {tx_hash!r}"

    # Confirm an escrow was registered in the factory
    escrow_addr = await _get_latest_escrow(client)
    assert AsyncWeb3.is_address(escrow_addr)

    # Confirm the escrow is funded with the budget cap
    deal = await client.get_deal_state(escrow_addr)
    assert deal.state == EscrowState.Funded
    assert deal.balance_wei == BUDGET_CAP_WEI
    assert deal.budget_cap_wei == BUDGET_CAP_WEI
    assert deal.reserve_price_wei == RESERVE_PRICE_WEI


@pytest.mark.asyncio
async def test_full_lifecycle(client):
    """Create → submit outcome → seller accepts → seller paid, escrow drained."""
    # 1. Create deal
    await client.create_deal(
        seller_address=SELLER_ADDR,
        operator_address=OPERATOR_ADDR,
        reserve_price_wei=RESERVE_PRICE_WEI,
        deadline=_deadline_future(),
        budget_cap_wei=BUDGET_CAP_WEI,
        private_key=BUYER_KEY,
    )
    escrow_addr = await _get_latest_escrow(client)

    # Capture seller balance before accept
    w3 = AsyncWeb3(AsyncHTTPProvider(ANVIL_RPC))
    seller_balance_before = await w3.eth.get_balance(
        AsyncWeb3.to_checksum_address(SELLER_ADDR)
    )

    # 2. Operator submits outcome
    attestation_hash = EscrowClient.compute_attestation_hash(
        pcr0=b"\x00" * 48,
        nonce=b"test-nonce",
        outcome=b"deal-accepted",
    )
    await client.submit_outcome(
        escrow_address=escrow_addr,
        final_price_wei=FINAL_PRICE_WEI,
        attestation_hash=attestation_hash,
        private_key=OPERATOR_KEY,
    )

    deal = await client.get_deal_state(escrow_addr)
    assert deal.state == EscrowState.Evaluated
    assert deal.final_price_wei == FINAL_PRICE_WEI

    # 3. Seller accepts deal
    await client.accept_deal(
        escrow_address=escrow_addr,
        private_key=SELLER_KEY,
    )

    deal = await client.get_deal_state(escrow_addr)
    assert deal.state == EscrowState.Accepted

    # Escrow balance is 0 after payout
    assert deal.balance_wei == 0

    # Seller received the final price (minus gas — just check a significant increase)
    seller_balance_after = await w3.eth.get_balance(
        AsyncWeb3.to_checksum_address(SELLER_ADDR)
    )
    net_gain = seller_balance_after - seller_balance_before
    # Net gain should be close to FINAL_PRICE_WEI (allow for gas costs)
    assert net_gain > FINAL_PRICE_WEI * 9 // 10, (
        f"Seller net gain {net_gain} is less than 90% of final price {FINAL_PRICE_WEI}"
    )


@pytest.mark.asyncio
async def test_reject_lifecycle(client):
    """Create → submit outcome → seller rejects → buyer refunded."""
    # 1. Create deal
    await client.create_deal(
        seller_address=SELLER_ADDR,
        operator_address=OPERATOR_ADDR,
        reserve_price_wei=RESERVE_PRICE_WEI,
        deadline=_deadline_future(),
        budget_cap_wei=BUDGET_CAP_WEI,
        private_key=BUYER_KEY,
    )
    escrow_addr = await _get_latest_escrow(client)

    w3 = AsyncWeb3(AsyncHTTPProvider(ANVIL_RPC))
    buyer_balance_before = await w3.eth.get_balance(
        AsyncWeb3.to_checksum_address(BUYER_ADDR)
    )

    # 2. Operator submits outcome
    attestation_hash = EscrowClient.compute_attestation_hash(
        pcr0=b"\x00" * 48,
        nonce=b"reject-nonce",
        outcome=b"deal-rejected",
    )
    await client.submit_outcome(
        escrow_address=escrow_addr,
        final_price_wei=FINAL_PRICE_WEI,
        attestation_hash=attestation_hash,
        private_key=OPERATOR_KEY,
    )

    deal = await client.get_deal_state(escrow_addr)
    assert deal.state == EscrowState.Evaluated

    # 3. Seller rejects deal
    await client.reject_deal(
        escrow_address=escrow_addr,
        private_key=SELLER_KEY,
    )

    deal = await client.get_deal_state(escrow_addr)
    assert deal.state == EscrowState.Rejected

    # Escrow balance is 0 after refund
    assert deal.balance_wei == 0

    # Buyer was refunded the full budget cap
    buyer_balance_after = await w3.eth.get_balance(
        AsyncWeb3.to_checksum_address(BUYER_ADDR)
    )
    net_gain = buyer_balance_after - buyer_balance_before
    # Net gain ≈ BUDGET_CAP_WEI (buyer already spent on create_deal gas; refund is full balance)
    assert net_gain > BUDGET_CAP_WEI * 9 // 10, (
        f"Buyer net gain {net_gain} is less than 90% of budget cap {BUDGET_CAP_WEI}"
    )


@pytest.mark.asyncio
async def test_verify_attestation(client):
    """Create → submit outcome with known hash → verify attestation matches on-chain."""
    # Known attestation inputs
    pcr0    = b"\xab" * 48
    nonce   = b"known-nonce-42"
    outcome = b"outcome-data-xyz"

    expected_hash = EscrowClient.compute_attestation_hash(pcr0, nonce, outcome)

    # 1. Create deal
    await client.create_deal(
        seller_address=SELLER_ADDR,
        operator_address=OPERATOR_ADDR,
        reserve_price_wei=RESERVE_PRICE_WEI,
        deadline=_deadline_future(),
        budget_cap_wei=BUDGET_CAP_WEI,
        private_key=BUYER_KEY,
    )
    escrow_addr = await _get_latest_escrow(client)

    # 2. Operator submits outcome with the known hash
    await client.submit_outcome(
        escrow_address=escrow_addr,
        final_price_wei=FINAL_PRICE_WEI,
        attestation_hash=expected_hash,
        private_key=OPERATOR_KEY,
    )

    # 3. Verify the stored attestation hash matches our inputs
    matches = await client.verify_attestation(
        escrow_address=escrow_addr,
        pcr0=pcr0,
        nonce=nonce,
        outcome=outcome,
    )
    assert matches, "verify_attestation returned False — on-chain hash does not match inputs"

    # Also verify raw stored hash equals expected
    deal = await client.get_deal_state(escrow_addr)
    assert deal.attestation_hash == expected_hash, (
        f"Stored hash {deal.attestation_hash.hex()} != expected {expected_hash.hex()}"
    )
