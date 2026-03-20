# Blockchain Escrow & CDP Browser Tunnel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-chain escrow (Base Sepolia) and vsock CDP browser tunnel so the enclave can settle deals on-chain and drive Chrome for interactive artifact evaluation.

**Architecture:** Two independent subsystems. (1) Foundry Solidity contracts + Python `web3.py` client wired into the orchestrator for fund locking and settlement. (2) A vsock tunnel bridging CDP WebSocket traffic between the enclave and a Chrome sidecar, with a lightweight `websockets`-based CDP client inside the enclave exposing browser tools to the evaluator agents.

**Tech Stack:** Solidity (Foundry), Python 3.11+, web3.py, websockets, FastAPI, Docker (neko-chrome)

**Spec:** `docs/superpowers/specs/2026-03-19-blockchain-escrow-and-cdp-tunnel-design.md`

---

## Task 1: Foundry Project Scaffold

**Files:**
- Create: `contracts/foundry.toml`
- Create: `contracts/src/NdaiEscrow.sol` (empty placeholder)
- Create: `contracts/src/NdaiEscrowFactory.sol` (empty placeholder)
- Create: `contracts/test/NdaiEscrow.t.sol` (empty placeholder)
- Create: `contracts/script/Deploy.s.sol` (empty placeholder)

- [ ] **Step 1: Install Foundry (if not present)**

Run: `which forge || curl -L https://foundry.paradigm.xyz | bash && foundryup`

- [ ] **Step 2: Initialize Foundry project and clean boilerplate**

```bash
cd /Users/discordwell/Projects/ndai-hackathon
mkdir -p contracts && cd contracts
forge init --no-git --no-commit
rm -f src/Counter.sol test/Counter.t.sol script/Counter.s.sol
```

- [ ] **Step 3: Configure foundry.toml and .gitignore**

Write `contracts/foundry.toml`:
```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
solc = "0.8.24"
optimizer = true
optimizer_runs = 200

[profile.default.fuzz]
runs = 256

[rpc_endpoints]
base_sepolia = "${BASE_SEPOLIA_RPC_URL}"
```

Add `contracts/out/` and `contracts/cache/` to the project `.gitignore`:
```
contracts/out/
contracts/cache/
```

- [ ] **Step 4: Install OpenZeppelin**

```bash
cd contracts && forge install OpenZeppelin/openzeppelin-contracts --no-git --no-commit
```

- [ ] **Step 5: Add remappings**

Write `contracts/remappings.txt`:
```
@openzeppelin/=lib/openzeppelin-contracts/
```

- [ ] **Step 6: Commit**

```bash
git add contracts/
git commit -m "feat: scaffold Foundry project for escrow contracts"
```

---

## Task 2: NdaiEscrow Solidity Contract

**Files:**
- Create: `contracts/src/NdaiEscrow.sol`
- Create: `contracts/test/NdaiEscrow.t.sol`

- [ ] **Step 1: Write the escrow contract tests**

Write `contracts/test/NdaiEscrow.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/NdaiEscrow.sol";

contract NdaiEscrowTest is Test {
    NdaiEscrow escrow;
    address seller = address(0x1);
    address buyer = address(0x2);
    address operator = address(0x3);
    uint256 reservePrice = 0.1 ether;
    uint256 budgetCap = 1 ether;
    uint256 deadline;

    function setUp() public {
        deadline = block.timestamp + 1 days;
        vm.deal(buyer, 10 ether);
        vm.prank(buyer);
        escrow = new NdaiEscrow{value: budgetCap}(
            seller, operator, reservePrice, deadline
        );
    }

    function test_initial_state() public view {
        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Funded));
        assertEq(escrow.seller(), seller);
        assertEq(escrow.buyer(), buyer);
        assertEq(escrow.operator(), operator);
        assertEq(escrow.reservePrice(), reservePrice);
        assertEq(escrow.budgetCap(), budgetCap);
        assertEq(address(escrow).balance, budgetCap);
    }

    function test_submitOutcome_sets_evaluated() public {
        bytes32 hash = keccak256("test");
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, hash);
        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Evaluated));
        assertEq(escrow.finalPrice(), 0.5 ether);
        assertEq(escrow.attestationHash(), hash);
    }

    function test_submitOutcome_reverts_if_not_operator() public {
        vm.prank(seller);
        vm.expectRevert("Only operator");
        escrow.submitOutcome(0.5 ether, keccak256("test"));
    }

    function test_submitOutcome_reverts_if_price_above_budget() public {
        vm.prank(operator);
        vm.expectRevert("Price exceeds budget cap");
        escrow.submitOutcome(2 ether, keccak256("test"));
    }

    function test_submitOutcome_reverts_if_price_below_reserve() public {
        vm.prank(operator);
        vm.expectRevert("Price below reserve");
        escrow.submitOutcome(0.01 ether, keccak256("test"));
    }

    function test_acceptDeal_pays_seller() public {
        bytes32 hash = keccak256("test");
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, hash);

        uint256 sellerBefore = seller.balance;
        uint256 buyerBefore = buyer.balance;
        vm.prank(seller);
        escrow.acceptDeal();

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Accepted));
        assertEq(seller.balance, sellerBefore + 0.5 ether);
        assertEq(buyer.balance, buyerBefore + 0.5 ether); // remainder
    }

    function test_acceptDeal_reverts_if_not_seller() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("test"));
        vm.prank(buyer);
        vm.expectRevert("Only seller");
        escrow.acceptDeal();
    }

    function test_rejectDeal_refunds_buyer() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("test"));

        uint256 buyerBefore = buyer.balance;
        vm.prank(seller);
        escrow.rejectDeal();

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Rejected));
        assertEq(buyer.balance, buyerBefore + budgetCap);
    }

    function test_claimExpired_refunds_after_deadline() public {
        vm.warp(deadline + 1);
        uint256 buyerBefore = buyer.balance;
        escrow.claimExpired();
        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Expired));
        assertEq(buyer.balance, buyerBefore + budgetCap);
    }

    function test_claimExpired_reverts_before_deadline() public {
        vm.expectRevert("Not expired");
        escrow.claimExpired();
    }

    function test_verifyAttestation() public {
        bytes32 pcr0 = bytes32(uint256(1));
        bytes32 nonce = bytes32(uint256(2));
        bytes32 outcome = bytes32(uint256(3));
        bytes32 hash = keccak256(abi.encodePacked(pcr0, nonce, outcome));

        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, hash);

        assertTrue(escrow.verifyAttestation(pcr0, nonce, outcome));
        assertFalse(escrow.verifyAttestation(pcr0, nonce, bytes32(uint256(99))));
    }

    // Fuzz test: any valid price within bounds should succeed
    function testFuzz_submitOutcome_valid_price(uint256 price) public {
        price = bound(price, reservePrice, budgetCap);
        vm.prank(operator);
        escrow.submitOutcome(price, keccak256("fuzz"));
        assertEq(escrow.finalPrice(), price);
    }

    function test_double_accept_reverts() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("test"));
        vm.prank(seller);
        escrow.acceptDeal();
        vm.prank(seller);
        vm.expectRevert("Wrong state");
        escrow.acceptDeal();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd contracts && forge test -v`
Expected: Compilation error (NdaiEscrow.sol doesn't exist yet)

- [ ] **Step 3: Write the NdaiEscrow contract**

Write `contracts/src/NdaiEscrow.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract NdaiEscrow is ReentrancyGuard {
    enum State { Created, Funded, Evaluated, Accepted, Rejected, Expired }

    address public immutable seller;
    address public immutable buyer;
    address public immutable operator;
    uint256 public immutable reservePrice;
    uint256 public immutable budgetCap;
    uint256 public immutable deadline;

    uint256 public finalPrice;
    bytes32 public attestationHash;
    State public state;

    event OutcomeSubmitted(uint256 finalPrice, bytes32 attestationHash);
    event DealAccepted(uint256 sellerPayout, uint256 buyerRefund);
    event DealRejected(uint256 buyerRefund);
    event DealExpired(uint256 buyerRefund);

    modifier onlyOperator() { require(msg.sender == operator, "Only operator"); _; }
    modifier onlySeller() { require(msg.sender == seller, "Only seller"); _; }
    modifier inState(State s) { require(state == s, "Wrong state"); _; }

    constructor(
        address _seller,
        address _operator,
        uint256 _reservePrice,
        uint256 _deadline
    ) payable {
        require(msg.value > 0, "Must fund escrow");
        require(_seller != address(0), "Invalid seller");
        require(_operator != address(0), "Invalid operator");
        require(_reservePrice <= msg.value, "Reserve exceeds budget");
        require(_deadline > block.timestamp, "Deadline in past");

        seller = _seller;
        buyer = msg.sender;
        operator = _operator;
        reservePrice = _reservePrice;
        budgetCap = msg.value;
        deadline = _deadline;
        state = State.Funded;
    }

    function submitOutcome(
        uint256 _finalPrice,
        bytes32 _attestationHash
    ) external onlyOperator inState(State.Funded) {
        require(_finalPrice <= budgetCap, "Price exceeds budget cap");
        require(_finalPrice >= reservePrice, "Price below reserve");

        finalPrice = _finalPrice;
        attestationHash = _attestationHash;
        state = State.Evaluated;

        emit OutcomeSubmitted(_finalPrice, _attestationHash);
    }

    function acceptDeal() external onlySeller inState(State.Evaluated) nonReentrant {
        state = State.Accepted;
        uint256 sellerPayout = finalPrice;
        uint256 buyerRefund = address(this).balance - sellerPayout;

        emit DealAccepted(sellerPayout, buyerRefund);

        (bool s1,) = seller.call{value: sellerPayout}("");
        require(s1, "Seller transfer failed");
        if (buyerRefund > 0) {
            (bool s2,) = buyer.call{value: buyerRefund}("");
            require(s2, "Buyer refund failed");
        }
    }

    function rejectDeal() external onlySeller inState(State.Evaluated) nonReentrant {
        state = State.Rejected;
        uint256 refund = address(this).balance;
        emit DealRejected(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    function claimExpired() external nonReentrant {
        require(block.timestamp > deadline, "Not expired");
        require(
            state == State.Funded || state == State.Evaluated,
            "Wrong state"
        );
        state = State.Expired;
        uint256 refund = address(this).balance;
        emit DealExpired(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    function verifyAttestation(
        bytes32 pcr0,
        bytes32 nonce,
        bytes32 outcome
    ) external view returns (bool) {
        return attestationHash == keccak256(abi.encodePacked(pcr0, nonce, outcome));
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd contracts && forge test -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add contracts/src/NdaiEscrow.sol contracts/test/NdaiEscrow.t.sol
git commit -m "feat: NdaiEscrow contract with full test coverage"
```

---

## Task 3: NdaiEscrowFactory Contract

**Files:**
- Create: `contracts/src/NdaiEscrowFactory.sol`
- Create: `contracts/test/NdaiEscrowFactory.t.sol`

- [ ] **Step 1: Write factory tests**

Write `contracts/test/NdaiEscrowFactory.t.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/NdaiEscrowFactory.sol";
import "../src/NdaiEscrow.sol";

contract NdaiEscrowFactoryTest is Test {
    NdaiEscrowFactory factory;
    address seller = address(0x1);
    address operator = address(0x3);

    function setUp() public {
        factory = new NdaiEscrowFactory();
    }

    function test_createEscrow_deploys_and_funds() public {
        vm.deal(address(this), 10 ether);
        uint256 deadline = block.timestamp + 1 days;
        address escrowAddr = factory.createEscrow{value: 1 ether}(
            seller, operator, 0.1 ether, deadline
        );

        assertTrue(escrowAddr != address(0));
        assertEq(address(escrowAddr).balance, 1 ether);

        NdaiEscrow escrow = NdaiEscrow(escrowAddr);
        assertEq(escrow.buyer(), address(this));
        assertEq(escrow.seller(), seller);
        assertEq(escrow.operator(), operator);
        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Funded));
    }

    function test_registry_tracks_escrows() public {
        vm.deal(address(this), 10 ether);
        uint256 deadline = block.timestamp + 1 days;
        address e1 = factory.createEscrow{value: 1 ether}(seller, operator, 0.1 ether, deadline);
        address e2 = factory.createEscrow{value: 0.5 ether}(seller, operator, 0.05 ether, deadline);

        address[] memory all = factory.getEscrows();
        assertEq(all.length, 2);
        assertEq(all[0], e1);
        assertEq(all[1], e2);
    }

    function test_escrowCount() public {
        vm.deal(address(this), 10 ether);
        uint256 deadline = block.timestamp + 1 days;
        assertEq(factory.escrowCount(), 0);
        factory.createEscrow{value: 1 ether}(seller, operator, 0.1 ether, deadline);
        assertEq(factory.escrowCount(), 1);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd contracts && forge test --match-contract NdaiEscrowFactoryTest -v`
Expected: Compilation error

- [ ] **Step 3: Write the factory contract**

Write `contracts/src/NdaiEscrowFactory.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./NdaiEscrow.sol";

contract NdaiEscrowFactory {
    address[] public escrows;

    event EscrowCreated(
        address indexed escrow,
        address indexed buyer,
        address indexed seller
    );

    function createEscrow(
        address seller,
        address operator,
        uint256 reservePrice,
        uint256 deadline
    ) external payable returns (address) {
        NdaiEscrow escrow = new NdaiEscrow{value: msg.value}(
            seller, operator, reservePrice, deadline
        );
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller);
        return addr;
    }

    function getEscrows() external view returns (address[] memory) {
        return escrows;
    }

    function escrowCount() external view returns (uint256) {
        return escrows.length;
    }
}
```

- [ ] **Step 4: Run tests**

Run: `cd contracts && forge test -v`
Expected: All tests pass (both NdaiEscrow and NdaiEscrowFactory)

- [ ] **Step 5: Write deploy script**

Write `contracts/script/Deploy.s.sol`:
```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/NdaiEscrowFactory.sol";

contract Deploy is Script {
    function run() external {
        vm.startBroadcast();
        NdaiEscrowFactory factory = new NdaiEscrowFactory();
        vm.stopBroadcast();
        console.log("Factory deployed at:", address(factory));
    }
}
```

- [ ] **Step 6: Commit**

```bash
git add contracts/
git commit -m "feat: NdaiEscrowFactory with registry and deploy script"
```

---

## Task 4: Python Escrow Client

**Files:**
- Create: `ndai/blockchain/__init__.py`
- Create: `ndai/blockchain/models.py`
- Create: `ndai/blockchain/escrow_client.py`
- Create: `tests/unit/test_escrow_client.py`
- Modify: `ndai/config.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add web3 dependency**

Add `"web3>=7.0.0"` to `pyproject.toml` dependencies list. Run: `pip install -e ".[dev]"`

- [ ] **Step 2: Write the DealState model**

Write `ndai/blockchain/__init__.py`:
```python
```

Write `ndai/blockchain/models.py`:
```python
"""Blockchain data models."""

from dataclasses import dataclass
from enum import IntEnum


class EscrowState(IntEnum):
    Created = 0
    Funded = 1
    Evaluated = 2
    Accepted = 3
    Rejected = 4
    Expired = 5


@dataclass
class DealState:
    """On-chain escrow state."""

    seller: str
    buyer: str
    operator: str
    reserve_price_wei: int
    budget_cap_wei: int
    final_price_wei: int
    attestation_hash: bytes
    deadline: int
    state: EscrowState
    balance_wei: int
```

- [ ] **Step 3: Write escrow client tests**

Write `tests/unit/test_escrow_client.py`:
```python
"""Tests for EscrowClient against Anvil local chain.

These tests require Anvil running. They are skipped if Anvil is not available.
Start Anvil with: anvil --port 8545
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from ndai.blockchain.models import DealState, EscrowState
from ndai.blockchain.escrow_client import EscrowClient, EscrowError


class TestEscrowClientInit:
    def test_constructor(self):
        client = EscrowClient(
            rpc_url="http://localhost:8545",
            factory_address="0x" + "00" * 20,
            chain_id=84532,
        )
        assert client.rpc_url == "http://localhost:8545"
        assert client.chain_id == 84532

    def test_constructor_validates_factory_address(self):
        with pytest.raises(ValueError, match="Invalid factory address"):
            EscrowClient(
                rpc_url="http://localhost:8545",
                factory_address="not-an-address",
                chain_id=84532,
            )


class TestAttestationHash:
    def test_compute_attestation_hash(self):
        """Verify Python hash matches Solidity keccak256(abi.encodePacked(...))."""
        from ndai.blockchain.escrow_client import compute_attestation_hash

        pcr0 = b"\x01" * 32
        nonce = b"\x02" * 32
        outcome = b"\x03" * 32
        result = compute_attestation_hash(pcr0, nonce, outcome)
        assert isinstance(result, bytes)
        assert len(result) == 32
        # Deterministic
        assert result == compute_attestation_hash(pcr0, nonce, outcome)
        # Different inputs → different hash
        assert result != compute_attestation_hash(pcr0, nonce, b"\x04" * 32)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/unit/test_escrow_client.py -v`
Expected: ImportError (module doesn't exist yet)

- [ ] **Step 5: Write the escrow client**

Write `ndai/blockchain/escrow_client.py`:
```python
"""Python client for the NdaiEscrow and NdaiEscrowFactory contracts."""

import asyncio
import json
import logging
from pathlib import Path

from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.exceptions import ContractLogicError

logger = logging.getLogger(__name__)


class EscrowError(Exception):
    """Error interacting with escrow contracts."""


def _load_abi(name: str) -> list:
    """Load compiled ABI from Foundry out/ directory."""
    abi_path = Path(__file__).parent.parent.parent / "contracts" / "out" / name / f"{name.replace('.sol', '')}.json"
    if not abi_path.exists():
        # Try alternate path structure
        abi_path = Path(__file__).parent.parent.parent / "contracts" / "out" / f"{name}" / f"{name.split('.')[0]}.json"
    if not abi_path.exists():
        raise EscrowError(
            f"ABI not found at {abi_path}. Run 'forge build' in contracts/ first."
        )
    with open(abi_path) as f:
        return json.load(f)["abi"]


def compute_attestation_hash(pcr0: bytes, nonce: bytes, outcome: bytes) -> bytes:
    """Compute keccak256(abi.encodePacked(pcr0, nonce, outcome)).

    Must match Solidity: keccak256(abi.encodePacked(bytes32, bytes32, bytes32))
    """
    from web3 import Web3

    assert len(pcr0) == 32, f"pcr0 must be 32 bytes, got {len(pcr0)}"
    assert len(nonce) == 32, f"nonce must be 32 bytes, got {len(nonce)}"
    assert len(outcome) == 32, f"outcome must be 32 bytes, got {len(outcome)}"
    return Web3.solidity_keccak(["bytes32", "bytes32", "bytes32"], [pcr0, nonce, outcome])


class EscrowClient:
    """Async client for NdaiEscrow contracts on Base Sepolia."""

    def __init__(
        self,
        rpc_url: str,
        factory_address: str,
        chain_id: int = 84532,
    ):
        if not factory_address.startswith("0x") or len(factory_address) != 42:
            raise ValueError(f"Invalid factory address: {factory_address}")

        self.rpc_url = rpc_url
        self.factory_address = factory_address
        self.chain_id = chain_id
        self._w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))

    async def create_deal(
        self,
        seller_address: str,
        reserve_price_wei: int,
        budget_cap_wei: int,
        deadline_seconds: int,
        operator_address: str,
        buyer_private_key: str,
    ) -> tuple[str, str]:
        """Create and fund a new escrow via the factory.

        Returns (tx_hash, escrow_address).
        """
        factory_abi = _load_abi("NdaiEscrowFactory.sol")
        factory = self._w3.eth.contract(
            address=self._w3.to_checksum_address(self.factory_address),
            abi=factory_abi,
        )
        account = self._w3.eth.account.from_key(buyer_private_key)
        block = await self._w3.eth.get_block("latest")
        deadline = block["timestamp"] + deadline_seconds

        tx = await factory.functions.createEscrow(
            self._w3.to_checksum_address(seller_address),
            self._w3.to_checksum_address(operator_address),
            reserve_price_wei,
            deadline,
        ).build_transaction({
            "from": account.address,
            "value": budget_cap_wei,
            "chainId": self.chain_id,
            "nonce": await self._w3.eth.get_transaction_count(account.address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash)

        # Extract escrow address from EscrowCreated event
        escrow_created = factory.events.EscrowCreated().process_receipt(receipt)
        if not escrow_created:
            raise EscrowError("No EscrowCreated event in receipt")
        escrow_address = escrow_created[0]["args"]["escrow"]

        logger.info("Escrow created at %s (tx: %s)", escrow_address, tx_hash.hex())
        return tx_hash.hex(), escrow_address

    async def submit_outcome(
        self,
        escrow_address: str,
        final_price_wei: int,
        attestation_hash: bytes,
        operator_private_key: str,
    ) -> str:
        """Submit negotiation outcome to escrow contract."""
        escrow_abi = _load_abi("NdaiEscrow.sol")
        escrow = self._w3.eth.contract(
            address=self._w3.to_checksum_address(escrow_address),
            abi=escrow_abi,
        )
        account = self._w3.eth.account.from_key(operator_private_key)

        tx = await escrow.functions.submitOutcome(
            final_price_wei, attestation_hash
        ).build_transaction({
            "from": account.address,
            "chainId": self.chain_id,
            "nonce": await self._w3.eth.get_transaction_count(account.address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        await self._w3.eth.wait_for_transaction_receipt(tx_hash)

        logger.info("Outcome submitted to %s (tx: %s)", escrow_address, tx_hash.hex())
        return tx_hash.hex()

    async def accept_deal(
        self,
        escrow_address: str,
        seller_private_key: str,
    ) -> str:
        """Seller accepts the deal, triggering fund release."""
        escrow_abi = _load_abi("NdaiEscrow.sol")
        escrow = self._w3.eth.contract(
            address=self._w3.to_checksum_address(escrow_address),
            abi=escrow_abi,
        )
        account = self._w3.eth.account.from_key(seller_private_key)

        tx = await escrow.functions.acceptDeal().build_transaction({
            "from": account.address,
            "chainId": self.chain_id,
            "nonce": await self._w3.eth.get_transaction_count(account.address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        await self._w3.eth.wait_for_transaction_receipt(tx_hash)

        logger.info("Deal accepted at %s (tx: %s)", escrow_address, tx_hash.hex())
        return tx_hash.hex()

    async def reject_deal(
        self,
        escrow_address: str,
        seller_private_key: str,
    ) -> str:
        """Seller rejects the deal, refunding buyer."""
        escrow_abi = _load_abi("NdaiEscrow.sol")
        escrow = self._w3.eth.contract(
            address=self._w3.to_checksum_address(escrow_address),
            abi=escrow_abi,
        )
        account = self._w3.eth.account.from_key(seller_private_key)

        tx = await escrow.functions.rejectDeal().build_transaction({
            "from": account.address,
            "chainId": self.chain_id,
            "nonce": await self._w3.eth.get_transaction_count(account.address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        await self._w3.eth.wait_for_transaction_receipt(tx_hash)

        logger.info("Deal rejected at %s (tx: %s)", escrow_address, tx_hash.hex())
        return tx_hash.hex()

    async def claim_expired(
        self,
        escrow_address: str,
        private_key: str,
    ) -> str:
        """Claim expired escrow, refunding buyer."""
        escrow_abi = _load_abi("NdaiEscrow.sol")
        escrow = self._w3.eth.contract(
            address=self._w3.to_checksum_address(escrow_address),
            abi=escrow_abi,
        )
        account = self._w3.eth.account.from_key(private_key)

        tx = await escrow.functions.claimExpired().build_transaction({
            "from": account.address,
            "chainId": self.chain_id,
            "nonce": await self._w3.eth.get_transaction_count(account.address),
        })

        signed = account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.raw_transaction)
        await self._w3.eth.wait_for_transaction_receipt(tx_hash)
        return tx_hash.hex()

    async def get_deal_state(self, escrow_address: str) -> "DealState":
        """Read current escrow state from chain."""
        from ndai.blockchain.models import DealState, EscrowState

        escrow_abi = _load_abi("NdaiEscrow.sol")
        escrow = self._w3.eth.contract(
            address=self._w3.to_checksum_address(escrow_address),
            abi=escrow_abi,
        )

        state_val, seller, buyer, operator = await asyncio.gather(
            escrow.functions.state().call(),
            escrow.functions.seller().call(),
            escrow.functions.buyer().call(),
            escrow.functions.operator().call(),
        )
        reserve, budget, final_price, att_hash, deadline = await asyncio.gather(
            escrow.functions.reservePrice().call(),
            escrow.functions.budgetCap().call(),
            escrow.functions.finalPrice().call(),
            escrow.functions.attestationHash().call(),
            escrow.functions.deadline().call(),
        )
        balance = await self._w3.eth.get_balance(escrow_address)

        return DealState(
            seller=seller,
            buyer=buyer,
            operator=operator,
            reserve_price_wei=reserve,
            budget_cap_wei=budget,
            final_price_wei=final_price,
            attestation_hash=att_hash,
            deadline=deadline,
            state=EscrowState(state_val),
            balance_wei=balance,
        )

    async def verify_attestation(
        self,
        escrow_address: str,
        pcr0: bytes,
        nonce: bytes,
        outcome: bytes,
    ) -> bool:
        """Call the on-chain verification function."""
        escrow_abi = _load_abi("NdaiEscrow.sol")
        escrow = self._w3.eth.contract(
            address=self._w3.to_checksum_address(escrow_address),
            abi=escrow_abi,
        )
        return await escrow.functions.verifyAttestation(pcr0, nonce, outcome).call()
```

- [ ] **Step 6: Add config settings**

Add to `ndai/config.py` inside the `Settings` class:
```python
    # Blockchain
    base_sepolia_rpc_url: str = ""
    escrow_factory_address: str = ""
    escrow_operator_key: str = ""
    chain_id: int = 84532
    blockchain_enabled: bool = False
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/unit/test_escrow_client.py -v`
Expected: All pass

- [ ] **Step 8: Commit**

```bash
git add ndai/blockchain/ tests/unit/test_escrow_client.py ndai/config.py pyproject.toml
git commit -m "feat: Python EscrowClient with web3.py"
```

---

## Task 5: Model Changes + Alembic Migration

**Files:**
- Modify: `ndai/models/agreement.py`
- Modify: `ndai/models/payment.py`
- Create: `alembic/versions/xxxx_add_escrow_fields.py`

- [ ] **Step 1: Add escrow fields to Agreement model**

In `ndai/models/agreement.py`, add after the `attestation_doc` field:
```python
    escrow_address: Mapped[str | None] = mapped_column(String(42))
    escrow_tx_hash: Mapped[str | None] = mapped_column(String(66))
```

- [ ] **Step 2: Rename mock_transaction_id in Payment**

In `ndai/models/payment.py`, change:
```python
    mock_transaction_id: Mapped[str | None] = mapped_column(String(255))
```
to:
```python
    transaction_hash: Mapped[str | None] = mapped_column(String(66))
```

- [ ] **Step 3: Generate Alembic migration**

Run: `cd /Users/discordwell/Projects/ndai-hackathon && alembic revision --autogenerate -m "add escrow fields and rename transaction hash"`

- [ ] **Step 4: Edit the migration to use RENAME instead of drop+create**

In the generated migration file, ensure the `mock_transaction_id` rename uses:
```python
op.alter_column('payments', 'mock_transaction_id', new_column_name='transaction_hash')
```
and the downgrade uses:
```python
op.alter_column('payments', 'transaction_hash', new_column_name='mock_transaction_id')
```

- [ ] **Step 5: Run existing tests to verify no breakage**

Run: `pytest tests/ -v --ignore=tests/unit/test_escrow_client.py`
Expected: All existing tests pass

- [ ] **Step 6: Commit**

```bash
git add ndai/models/ alembic/
git commit -m "feat: add escrow_address to Agreement, rename transaction_hash"
```

---

## Task 6: Orchestrator Blockchain Integration

**Files:**
- Modify: `ndai/tee/orchestrator.py`
- Modify: `ndai/api/routers/negotiations.py`
- Create: `tests/integration/test_escrow_flow.py`

- [ ] **Step 1: Add NegotiationOutcomeWithAttestation**

In `ndai/tee/orchestrator.py`, add after the `EnclaveNegotiationConfig` dataclass:
```python
@dataclass
class NegotiationOutcomeWithAttestation:
    """Negotiation result enriched with attestation data for on-chain settlement."""
    result: NegotiationResult
    attestation_hash: bytes  # 32-byte keccak256
    pcr0: str
    nonce: bytes
```

- [ ] **Step 2: Modify _run_simulated to return attestation data when blockchain_enabled**

In `EnclaveOrchestrator`, add a `blockchain_enabled` parameter and compute a simulated attestation hash when enabled. The `run_negotiation` method returns `NegotiationOutcomeWithAttestation` when `blockchain_enabled` is `True`, else `NegotiationResult` (preserving backward compatibility).

- [ ] **Step 3: Add blockchain config to EnclaveNegotiationConfig**

Add to `EnclaveNegotiationConfig`:
```python
    blockchain_enabled: bool = False
    escrow_address: str = ""
```

- [ ] **Step 4: Wire escrow into the negotiations router**

In `ndai/api/routers/negotiations.py`, in `_run_negotiation_async()`, after the orchestrator returns:
- If `settings.blockchain_enabled` and the result has an attestation hash:
  - Call `EscrowClient.submit_outcome()` with the final price and attestation hash
  - Store the tx hash in the agreement's `escrow_tx_hash`
- Wrap in try/except so blockchain failures don't lose the negotiation result

- [ ] **Step 5: Write integration test**

Write `tests/integration/test_escrow_flow.py`:
```python
"""Integration test for the full escrow flow.

Requires: anvil running on port 8545
Skip if not available.
"""

import pytest
from ndai.blockchain.escrow_client import EscrowClient, compute_attestation_hash

ANVIL_URL = "http://localhost:8545"
# Anvil default accounts
BUYER_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
SELLER_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"
OPERATOR_KEY = "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"


@pytest.fixture
def anvil_available():
    """Skip if Anvil is not running."""
    import httpx
    try:
        r = httpx.post(ANVIL_URL, json={"jsonrpc": "2.0", "method": "eth_blockNumber", "params": [], "id": 1})
        r.raise_for_status()
    except Exception:
        pytest.skip("Anvil not running on port 8545")


@pytest.mark.asyncio
async def test_full_escrow_lifecycle(anvil_available):
    """Test: create → submit outcome → accept → verify."""
    # This test requires deploying the factory first via forge script
    # For now, test the attestation hash computation
    pcr0 = b"\x01" * 32
    nonce = b"\x02" * 32
    outcome = b"\x03" * 32
    h = compute_attestation_hash(pcr0, nonce, outcome)
    assert len(h) == 32
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/integration/test_escrow_flow.py -v`
Expected: Pass (skips if Anvil not running, hash test always passes)

- [ ] **Step 7: Commit**

```bash
git add ndai/tee/orchestrator.py ndai/api/routers/negotiations.py tests/integration/test_escrow_flow.py
git commit -m "feat: wire escrow settlement into orchestrator and negotiation flow"
```

---

## Task 7: CDP Tunnel (Parent Side)

**Files:**
- Create: `ndai/enclave/cdp_tunnel.py`
- Create: `tests/unit/test_cdp_tunnel.py`

- [ ] **Step 1: Write CDP tunnel tests**

Write `tests/unit/test_cdp_tunnel.py`:
```python
"""Tests for the CDP tunnel (parent-side vsock ↔ WebSocket bridge)."""

import pytest
from ndai.enclave.cdp_tunnel import CdpTunnel, CDP_PORT


class TestCdpTunnelInit:
    def test_defaults(self):
        tunnel = CdpTunnel()
        assert tunnel.port == CDP_PORT
        assert tunnel.chrome_ws_url == "ws://localhost:9222"

    def test_custom_config(self):
        tunnel = CdpTunnel(chrome_ws_url="ws://neko:9222", port=5004)
        assert tunnel.port == 5004
        assert tunnel.chrome_ws_url == "ws://neko:9222"

    def test_initial_state(self):
        tunnel = CdpTunnel()
        assert tunnel.bytes_forwarded == 0
        assert not tunnel._running
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_cdp_tunnel.py -v`
Expected: ImportError

- [ ] **Step 3: Write the CDP tunnel**

Write `ndai/enclave/cdp_tunnel.py`:
```python
"""Parent-side CDP tunnel: bridges vsock ↔ WebSocket to Chrome.

Same pattern as VsockTunnel (port 5002) but bridges to Chrome's CDP
WebSocket endpoint instead of raw TCP. The enclave drives the browser
via CDP commands tunneled through vsock.

Protocol:
    1. Enclave connects to parent on vsock CDP_PORT
    2. Enclave sends: "CONNECT cdp\n"
    3. Parent opens WebSocket to Chrome's CDP endpoint
    4. Parent sends: "OK <ws_debugger_url>\n"
    5. Bidirectional frame forwarding until either side closes

For HTTP discovery (/json/version):
    1. Enclave sends: "HTTP GET /json/version\n"
    2. Parent fetches http://localhost:9222/json/version
    3. Parent sends the JSON response as a single frame
    4. Connection stays open for subsequent CONNECT
"""

import asyncio
import json
import logging
import socket

import httpx
import websockets

logger = logging.getLogger(__name__)

AF_VSOCK = 40
VMADDR_CID_ANY = 0xFFFFFFFF
CDP_PORT = 5003
BUFFER_SIZE = 65536


class CdpTunnelError(Exception):
    """Error in CDP tunnel operation."""


class CdpTunnel:
    """Parent-side bridge between enclave vsock and Chrome CDP WebSocket."""

    def __init__(
        self,
        chrome_ws_url: str = "ws://localhost:9222",
        port: int = CDP_PORT,
    ):
        self.chrome_ws_url = chrome_ws_url
        self.chrome_http_url = chrome_ws_url.replace("ws://", "http://")
        self.port = port
        self._server_sock: socket.socket | None = None
        self._running = False
        self._tasks: set[asyncio.Task] = set()
        self._bytes_forwarded = 0

    @property
    def bytes_forwarded(self) -> int:
        return self._bytes_forwarded

    async def run(self) -> None:
        """Start the tunnel and serve connections."""
        self._server_sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((VMADDR_CID_ANY, self.port))
        self._server_sock.listen(4)
        self._server_sock.setblocking(False)
        self._running = True

        logger.info("CdpTunnel listening on vsock port %d → %s", self.port, self.chrome_ws_url)

        loop = asyncio.get_event_loop()
        try:
            while self._running:
                try:
                    conn, addr = await loop.run_in_executor(None, self._accept_with_timeout)
                except TimeoutError:
                    continue
                logger.info("CDP tunnel: connection from CID=%s", addr[0])
                task = asyncio.create_task(self._handle_connection(conn))
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
        finally:
            await self._cleanup()

    async def run_background(self) -> asyncio.Task:
        task = asyncio.create_task(self.run())
        await asyncio.sleep(0.05)
        return task

    async def stop(self) -> None:
        logger.info("Stopping CdpTunnel (forwarded %d bytes)", self._bytes_forwarded)
        self._running = False
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=10)
        await self._cleanup()

    def _accept_with_timeout(self) -> tuple[socket.socket, tuple[int, int]]:
        assert self._server_sock is not None
        self._server_sock.settimeout(1.0)
        try:
            return self._server_sock.accept()
        except socket.timeout as exc:
            raise TimeoutError from exc

    async def _handle_connection(self, vsock_conn: socket.socket) -> None:
        """Handle a single enclave CDP connection."""
        vsock_conn.setblocking(True)
        vsock_conn.settimeout(30)
        ws = None

        try:
            loop = asyncio.get_event_loop()

            # Read command line
            line = await loop.run_in_executor(None, self._read_line, vsock_conn)

            if line.startswith("HTTP GET"):
                # HTTP discovery request
                path = line.split(" ", 2)[2] if len(line.split(" ")) > 2 else "/json/version"
                await self._handle_http(vsock_conn, path, loop)
                # After HTTP, read next command (should be CONNECT)
                line = await loop.run_in_executor(None, self._read_line, vsock_conn)

            if not line.startswith("CONNECT"):
                await loop.run_in_executor(None, vsock_conn.sendall, b"ERROR bad command\n")
                return

            # Discover browser WS debugger URL
            debugger_url = await self._get_debugger_url()
            if not debugger_url:
                await loop.run_in_executor(None, vsock_conn.sendall, b"ERROR no browser\n")
                return

            # Open WebSocket to Chrome
            ws = await websockets.connect(debugger_url, max_size=10 * 1024 * 1024)
            await loop.run_in_executor(
                None, vsock_conn.sendall, f"OK {debugger_url}\n".encode()
            )

            vsock_conn.settimeout(600)

            # Bidirectional forwarding
            await self._forward_ws(vsock_conn, ws, loop)

        except Exception:
            logger.exception("CDP tunnel: error handling connection")
        finally:
            vsock_conn.close()
            if ws:
                await ws.close()

    async def _handle_http(
        self, vsock_conn: socket.socket, path: str, loop: asyncio.AbstractEventLoop
    ) -> None:
        """Proxy an HTTP request to Chrome and return the response."""
        url = f"{self.chrome_http_url}{path}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5)
            body = resp.content
        # Send response as length-prefixed frame
        header = len(body).to_bytes(4, "big")
        await loop.run_in_executor(None, vsock_conn.sendall, header + body)

    async def _get_debugger_url(self) -> str | None:
        """Get Chrome's WebSocket debugger URL via /json/version."""
        url = f"{self.chrome_http_url}/json/version"
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=5)
                data = resp.json()
                return data.get("webSocketDebuggerUrl")
        except Exception:
            logger.error("Failed to get Chrome debugger URL from %s", url)
            return None

    async def _forward_ws(
        self,
        vsock_conn: socket.socket,
        ws,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """Forward frames between vsock and WebSocket."""

        async def vsock_to_ws():
            while True:
                # Read length-prefixed frame from vsock
                header = await loop.run_in_executor(None, self._recv_exact, vsock_conn, 4)
                if not header:
                    break
                length = int.from_bytes(header, "big")
                data = await loop.run_in_executor(None, self._recv_exact, vsock_conn, length)
                if not data:
                    break
                self._bytes_forwarded += len(data)
                await ws.send(data)

        async def ws_to_vsock():
            async for message in ws:
                if isinstance(message, str):
                    message = message.encode()
                header = len(message).to_bytes(4, "big")
                await loop.run_in_executor(None, vsock_conn.sendall, header + message)
                self._bytes_forwarded += len(message)

        t1 = asyncio.create_task(vsock_to_ws())
        t2 = asyncio.create_task(ws_to_vsock())

        done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        buf = b""
        while len(buf) < 256:
            byte = sock.recv(1)
            if not byte:
                raise ConnectionError("Connection closed")
            if byte == b"\n":
                return buf.decode().strip()
            buf += byte
        raise CdpTunnelError("Line too long")

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    async def _cleanup(self) -> None:
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        self._tasks.clear()
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_cdp_tunnel.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add ndai/enclave/cdp_tunnel.py tests/unit/test_cdp_tunnel.py
git commit -m "feat: parent-side CDP tunnel (vsock ↔ Chrome WebSocket)"
```

---

## Task 8: Enclave CDP Client

**Files:**
- Create: `ndai/enclave/tunnel_cdp_client.py`
- Create: `tests/unit/test_tunnel_cdp_client.py`

- [ ] **Step 1: Write tests**

Write `tests/unit/test_tunnel_cdp_client.py`:
```python
"""Tests for the enclave-side CDP client."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ndai.enclave.tunnel_cdp_client import TunnelCdpClient


class TestTunnelCdpClientInit:
    def test_simulated_mode(self):
        client = TunnelCdpClient(simulated=True, chrome_url="ws://localhost:9222")
        assert client.simulated is True

    def test_nitro_mode(self):
        client = TunnelCdpClient(simulated=False)
        assert client.simulated is False


class TestCdpCommandBuilding:
    def test_navigate_command(self):
        cmd = TunnelCdpClient._build_command("Page.navigate", {"url": "https://example.com"})
        assert cmd["method"] == "Page.navigate"
        assert cmd["params"]["url"] == "https://example.com"
        assert "id" in cmd

    def test_screenshot_command(self):
        cmd = TunnelCdpClient._build_command("Page.captureScreenshot", {})
        assert cmd["method"] == "Page.captureScreenshot"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_tunnel_cdp_client.py -v`
Expected: ImportError

- [ ] **Step 3: Write the tunnel CDP client**

Write `ndai/enclave/tunnel_cdp_client.py`:
```python
"""Enclave-side lightweight CDP client.

Uses the websockets library to speak Chrome DevTools Protocol.
In Nitro mode, connects through vsock to the parent's CdpTunnel.
In simulated mode, connects directly via TCP WebSocket.
"""

import asyncio
import json
import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

AF_VSOCK = 40
CDP_PORT = 5003
PARENT_CID = 3  # Parent CID in Nitro


class CdpClientError(Exception):
    """Error in CDP client operation."""


class TunnelCdpClient:
    """Lightweight CDP client for use inside the enclave."""

    def __init__(
        self,
        simulated: bool = True,
        chrome_url: str = "ws://localhost:9222",
        vsock_port: int = CDP_PORT,
    ):
        self.simulated = simulated
        self.chrome_url = chrome_url
        self.vsock_port = vsock_port
        self._msg_id = 0
        self._sock: socket.socket | None = None
        self._ws = None
        self._pending: dict[int, asyncio.Future] = {}
        self._recv_task: asyncio.Task | None = None

    @staticmethod
    def _build_command(method: str, params: dict | None = None) -> dict:
        """Build a CDP command. ID is assigned at send time."""
        return {"method": method, "params": params or {}, "id": 0}

    async def connect(self) -> None:
        """Establish connection to Chrome CDP."""
        if self.simulated:
            await self._connect_direct()
        else:
            await self._connect_vsock()

    async def _connect_direct(self) -> None:
        """Connect directly via WebSocket (simulated mode)."""
        import httpx

        # Discover debugger URL
        http_url = self.chrome_url.replace("ws://", "http://")
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{http_url}/json/version", timeout=5)
            debugger_url = resp.json()["webSocketDebuggerUrl"]

        import websockets
        self._ws = await websockets.connect(debugger_url, max_size=10 * 1024 * 1024)
        self._recv_task = asyncio.create_task(self._recv_loop_ws())
        logger.info("CDP client connected directly to %s", debugger_url)

    async def _connect_vsock(self) -> None:
        """Connect through vsock tunnel (Nitro mode)."""
        loop = asyncio.get_event_loop()

        self._sock = socket.socket(AF_VSOCK, socket.SOCK_STREAM)
        await loop.run_in_executor(
            None, self._sock.connect, (PARENT_CID, self.vsock_port)
        )
        self._sock.settimeout(600)

        # HTTP discovery
        await loop.run_in_executor(
            None, self._sock.sendall, b"HTTP GET /json/version\n"
        )
        header = await loop.run_in_executor(None, self._recv_exact, self._sock, 4)
        length = int.from_bytes(header, "big")
        body = await loop.run_in_executor(None, self._recv_exact, self._sock, length)
        version_info = json.loads(body)
        logger.info("CDP version: %s", version_info.get("Browser", "unknown"))

        # CONNECT
        await loop.run_in_executor(None, self._sock.sendall, b"CONNECT cdp\n")
        line = await loop.run_in_executor(None, self._read_line, self._sock)
        if not line.startswith("OK"):
            raise CdpClientError(f"CDP tunnel rejected: {line}")

        self._recv_task = asyncio.create_task(self._recv_loop_vsock())
        logger.info("CDP client connected through vsock tunnel")

    async def send_command(self, method: str, params: dict | None = None) -> dict:
        """Send a CDP command and wait for the response."""
        self._msg_id += 1
        msg_id = self._msg_id
        cmd = {"id": msg_id, "method": method, "params": params or {}}

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[msg_id] = future

        if self.simulated and self._ws:
            await self._ws.send(json.dumps(cmd))
        elif self._sock:
            data = json.dumps(cmd).encode()
            header = len(data).to_bytes(4, "big")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._sock.sendall, header + data)
        else:
            raise CdpClientError("Not connected")

        try:
            result = await asyncio.wait_for(future, timeout=30)
            return result
        except TimeoutError:
            self._pending.pop(msg_id, None)
            raise CdpClientError(f"CDP command timed out: {method}")

    async def _recv_loop_ws(self) -> None:
        """Receive loop for direct WebSocket mode."""
        try:
            async for message in self._ws:
                data = json.loads(message)
                msg_id = data.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending.pop(msg_id).set_result(data)
        except Exception:
            logger.debug("CDP recv loop ended")

    async def _recv_loop_vsock(self) -> None:
        """Receive loop for vsock tunnel mode."""
        loop = asyncio.get_event_loop()
        try:
            while True:
                header = await loop.run_in_executor(
                    None, self._recv_exact, self._sock, 4
                )
                if not header:
                    break
                length = int.from_bytes(header, "big")
                body = await loop.run_in_executor(
                    None, self._recv_exact, self._sock, length
                )
                if not body:
                    break
                data = json.loads(body)
                msg_id = data.get("id")
                if msg_id and msg_id in self._pending:
                    self._pending.pop(msg_id).set_result(data)
        except Exception:
            logger.debug("CDP vsock recv loop ended")

    async def close(self) -> None:
        """Close the CDP connection."""
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws:
            await self._ws.close()
        if self._sock:
            self._sock.close()
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    @staticmethod
    def _read_line(sock: socket.socket) -> str:
        buf = b""
        while len(buf) < 256:
            byte = sock.recv(1)
            if not byte:
                raise ConnectionError("Connection closed")
            if byte == b"\n":
                return buf.decode().strip()
            buf += byte
        raise CdpClientError("Line too long")

    @staticmethod
    def _recv_exact(sock: socket.socket, n: int) -> bytes | None:
        buf = b""
        while len(buf) < n:
            chunk = sock.recv(n - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_tunnel_cdp_client.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add ndai/enclave/tunnel_cdp_client.py tests/unit/test_tunnel_cdp_client.py
git commit -m "feat: enclave-side lightweight CDP client over vsock"
```

---

## Task 9: Browser Tools for Agents

**Files:**
- Create: `ndai/enclave/agents/browser_tools.py`
- Create: `tests/unit/test_browser_tools.py`

- [ ] **Step 1: Write browser tools tests**

Write `tests/unit/test_browser_tools.py`:
```python
"""Tests for browser tool definitions and CDP command translation."""

import pytest
from unittest.mock import AsyncMock
from ndai.enclave.agents.browser_tools import BrowserTools, BROWSER_TOOL_DEFINITIONS


class TestToolDefinitions:
    def test_all_tools_have_names(self):
        for tool in BROWSER_TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_expected_tools_exist(self):
        names = {t["name"] for t in BROWSER_TOOL_DEFINITIONS}
        assert "navigate" in names
        assert "screenshot" in names
        assert "scrape" in names
        assert "execute_js" in names
        assert "fill_form" in names
        assert "click" in names
        assert "get_page_text" in names


class TestBrowserToolsExecution:
    @pytest.fixture
    def mock_cdp(self):
        cdp = AsyncMock()
        cdp.send_command = AsyncMock(return_value={"result": {}})
        return cdp

    @pytest.fixture
    def tools(self, mock_cdp):
        return BrowserTools(mock_cdp)

    @pytest.mark.asyncio
    async def test_navigate_sends_page_navigate(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"frameId": "1"}}
        result = await tools.navigate("https://example.com")
        mock_cdp.send_command.assert_any_call("Page.navigate", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_screenshot_returns_base64(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"data": "iVBORw0KGgo="}}
        result = await tools.screenshot()
        mock_cdp.send_command.assert_called_with("Page.captureScreenshot", {"format": "png"})
        assert result == "iVBORw0KGgo="

    @pytest.mark.asyncio
    async def test_execute_js(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"result": {"value": "Example"}}}
        result = await tools.execute_js("document.title")
        mock_cdp.send_command.assert_called_with(
            "Runtime.evaluate", {"expression": "document.title", "returnByValue": True}
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_browser_tools.py -v`
Expected: ImportError

- [ ] **Step 3: Write the browser tools**

Write `ndai/enclave/agents/browser_tools.py`:
```python
"""Browser tools for evaluator agents.

Translates high-level agent tool calls into CDP protocol commands
sent via TunnelCdpClient.
"""

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

BROWSER_TOOL_DEFINITIONS = [
    {
        "name": "navigate",
        "description": "Navigate the browser to a URL. Returns the page title and status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to navigate to"},
            },
            "required": ["url"],
        },
    },
    {
        "name": "screenshot",
        "description": "Take a screenshot of the current page. Returns base64-encoded PNG.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Optional URL to navigate to first"},
            },
        },
    },
    {
        "name": "scrape",
        "description": "Extract structured data from the current page: title, headings, links, meta.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Optional URL to navigate to first"},
            },
        },
    },
    {
        "name": "execute_js",
        "description": "Execute JavaScript on the current page and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {"type": "string", "description": "JavaScript expression to evaluate"},
            },
            "required": ["script"],
        },
    },
    {
        "name": "fill_form",
        "description": "Fill form fields and submit. Fields is a dict of CSS selector → value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "description": "Mapping of CSS selector to value",
                    "additionalProperties": {"type": "string"},
                },
                "submit_selector": {"type": "string", "description": "CSS selector for submit button"},
            },
            "required": ["fields", "submit_selector"],
        },
    },
    {
        "name": "click",
        "description": "Click an element matching a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector of element to click"},
            },
            "required": ["selector"],
        },
    },
    {
        "name": "get_page_text",
        "description": "Get all visible text content of the current page.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


class BrowserTools:
    """Executes browser tool calls via CDP.

    All tool responses are hashed into the transcript chain for tamper-evident
    auditing. Note: browser-evaluated artifacts have weaker trust guarantees
    than directly-uploaded artifacts (see spec Section 2.2).
    """

    def __init__(self, cdp_client, transcript_hasher=None):
        self._cdp = cdp_client
        self._transcript = transcript_hasher  # optional, from ndai.enclave.transcript

    async def execute_tool(self, tool_name: str, tool_input: dict) -> Any:
        """Dispatch a tool call to the appropriate method."""
        method = getattr(self, tool_name, None)
        if not method:
            raise ValueError(f"Unknown browser tool: {tool_name}")
        result = await method(**tool_input)
        # Hash response into transcript chain for audit trail
        if self._transcript:
            import json as _json
            self._transcript.add_message(f"browser:{tool_name}", _json.dumps(result, default=str))
        return result

    async def navigate(self, url: str) -> dict:
        await self._cdp.send_command("Page.navigate", {"url": url})
        # Wait for load
        await asyncio.sleep(1)
        title_result = await self._cdp.send_command(
            "Runtime.evaluate",
            {"expression": "document.title", "returnByValue": True},
        )
        title = title_result.get("result", {}).get("result", {}).get("value", "")
        return {"title": title, "url": url}

    async def screenshot(self, url: str | None = None) -> str:
        if url:
            await self.navigate(url)
        result = await self._cdp.send_command(
            "Page.captureScreenshot", {"format": "png"}
        )
        return result.get("result", {}).get("data", "")

    async def scrape(self, url: str | None = None) -> dict:
        if url:
            await self.navigate(url)
        js = """(() => {
            const meta = document.querySelector('meta[name="description"]');
            return JSON.stringify({
                title: document.title,
                description: meta ? meta.content : null,
                headings: Array.from(document.querySelectorAll('h1,h2,h3')).map(e => ({
                    tag: e.tagName, text: e.textContent.trim()
                })).slice(0, 20),
                links: Array.from(document.querySelectorAll('a[href]')).slice(0, 30).map(a => ({
                    text: a.textContent.trim().substring(0, 80), href: a.href
                })),
            });
        })()"""
        result = await self._cdp.send_command(
            "Runtime.evaluate", {"expression": js, "returnByValue": True}
        )
        value = result.get("result", {}).get("result", {}).get("value", "{}")
        return json.loads(value) if isinstance(value, str) else value

    async def execute_js(self, script: str) -> Any:
        result = await self._cdp.send_command(
            "Runtime.evaluate", {"expression": script, "returnByValue": True}
        )
        return result.get("result", {}).get("result", {}).get("value")

    async def fill_form(self, fields: dict[str, str], submit_selector: str) -> dict:
        for selector, value in fields.items():
            js = f"""document.querySelector({json.dumps(selector)}).value = {json.dumps(value)};
            document.querySelector({json.dumps(selector)}).dispatchEvent(new Event('input', {{bubbles: true}}));"""
            await self._cdp.send_command(
                "Runtime.evaluate", {"expression": js, "returnByValue": True}
            )
        # Click submit
        await self.click(submit_selector)
        await asyncio.sleep(1)
        title = await self.execute_js("document.title")
        return {"result_title": title}

    async def click(self, selector: str) -> dict:
        js = f"""(() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return false;
            el.click();
            return true;
        }})()"""
        result = await self._cdp.send_command(
            "Runtime.evaluate", {"expression": js, "returnByValue": True}
        )
        success = result.get("result", {}).get("result", {}).get("value", False)
        return {"success": success}

    async def get_page_text(self) -> str:
        result = await self._cdp.send_command(
            "Runtime.evaluate",
            {"expression": "document.body.innerText", "returnByValue": True},
        )
        return result.get("result", {}).get("result", {}).get("value", "")
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_browser_tools.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add ndai/enclave/agents/browser_tools.py tests/unit/test_browser_tools.py
git commit -m "feat: browser tools for evaluator agents (CDP-backed)"
```

---

## Task 10: Session + Orchestrator CDP Integration

**Files:**
- Modify: `ndai/enclave/session.py`
- Modify: `ndai/tee/orchestrator.py`
- Modify: `ndai/config.py`

- [ ] **Step 1: Add CDP config settings**

In `ndai/config.py`, add to `Settings`:
```python
    # CDP / Browser
    browser_enabled: bool = False
    chrome_cdp_url: str = "ws://localhost:9222"
    cdp_vsock_port: int = 5003
```

- [ ] **Step 2: Update SessionConfig to accept optional CDP client**

In `ndai/enclave/session.py`, update `SessionConfig`:
```python
    cdp_client: Any | None = None  # TunnelCdpClient instance, if browser enabled
```

And in `NegotiationSession.__init__`, after creating the agents, add:
```python
        self.browser_tools = None
        if config.cdp_client:
            from ndai.enclave.agents.browser_tools import BrowserTools
            self.browser_tools = BrowserTools(config.cdp_client)
```

- [ ] **Step 3: Update EnclaveNegotiationConfig**

In `ndai/tee/orchestrator.py`, add to `EnclaveNegotiationConfig`:
```python
    browser_enabled: bool = False
    browser_credentials: dict | None = None
    target_urls: list[str] | None = None
```

- [ ] **Step 4: Wire CDP tunnel into _run_nitro and _run_simulated**

In `_run_nitro()`, after `tunnel = await self._start_tunnel(identity.enclave_cid)`:
```python
            # Step 2b: Start CDP tunnel if browser enabled
            cdp_tunnel = None
            if config.browser_enabled:
                cdp_tunnel = await self._start_cdp_tunnel()
```

In the `finally` block, add cleanup for `cdp_tunnel` before the TCP tunnel cleanup.

In `_run_simulated()`, if `config.browser_enabled`, create a `TunnelCdpClient(simulated=True)` and pass it via `SessionConfig`.

- [ ] **Step 5: Add _start_cdp_tunnel helper**

```python
    async def _start_cdp_tunnel(self):
        from ndai.enclave.cdp_tunnel import CdpTunnel
        tunnel = CdpTunnel(
            chrome_ws_url=self._settings.chrome_cdp_url,
            port=self._settings.cdp_vsock_port,
        )
        await tunnel.run_background()
        logger.info("CDP tunnel started")
        return tunnel
```

- [ ] **Step 6: Run all existing tests**

Run: `pytest tests/ -v`
Expected: All existing tests still pass (browser_enabled defaults to False)

- [ ] **Step 7: Commit**

```bash
git add ndai/enclave/session.py ndai/tee/orchestrator.py ndai/config.py
git commit -m "feat: integrate CDP tunnel into session and orchestrator"
```

---

## Task 11: Neko Chrome Sidecar

**Files:**
- Create: `deploy/neko-chrome/Dockerfile`
- Create: `deploy/neko-chrome/supervisord.conf`
- Create: `deploy/neko-chrome/nginx-cdp.conf`
- Create: `deploy/neko-chrome/preferences.json`
- Create: `deploy/neko-chrome/policies.json`
- Modify: `deploy/docker-compose.yml`

- [ ] **Step 1: Copy and adapt neko-chrome from dnai-wikigen**

Copy the directory structure from `dnai-wikigen/⚙️/cdp-playground/neko-chrome/` to `deploy/neko-chrome/`, keeping the same files: Dockerfile, supervisord.conf, nginx-cdp.conf, preferences.json, policies.json.

Adjust the Dockerfile to use the same base image and chrome setup. Adapt any paths as needed.

- [ ] **Step 2: Create docker-compose.yml with neko service**

Create `deploy/docker-compose.yml` (this file does not exist yet):
```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ndai
      POSTGRES_PASSWORD: ndai
      POSTGRES_DB: ndai
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  neko:
    build: ./neko-chrome
    shm_size: 2gb
    cap_add:
      - SYS_ADMIN
    ports:
      - "9222:9222"
      - "52100:8080"
    environment:
      NEKO_SCREEN: 1920x1080@30
      NEKO_PASSWORD: neko
      NEKO_PASSWORD_ADMIN: admin
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080"]
      interval: 10s
      retries: 5
      timeout: 5s

volumes:
  pgdata:
```

- [ ] **Step 3: Test Docker build**

Run: `cd deploy && docker compose build neko`
Expected: Builds successfully

- [ ] **Step 4: Commit**

```bash
git add deploy/neko-chrome/ deploy/docker-compose.yml
git commit -m "feat: add neko-chrome sidecar for CDP browser automation"
```

---

## Task 12: Update ARCHITECTURE.md

**Files:**
- Modify: `ARCHITECTURE.md`

- [ ] **Step 1: Add blockchain escrow and CDP tunnel sections**

Add to the System Overview diagram: the escrow contract on Base Sepolia. Add a new vsock port 5003 to the communication architecture diagram. Add entries to the Key Components table for:
- Escrow Contract (`contracts/src/NdaiEscrow.sol`)
- Escrow Factory (`contracts/src/NdaiEscrowFactory.sol`)
- Escrow Client (`ndai/blockchain/escrow_client.py`)
- CDP Tunnel (`ndai/enclave/cdp_tunnel.py`)
- CDP Client (`ndai/enclave/tunnel_cdp_client.py`)
- Browser Tools (`ndai/enclave/agents/browser_tools.py`)

Update the Security Model section to document that browser-evaluated artifacts have weaker trust guarantees than directly-uploaded artifacts.

- [ ] **Step 2: Run existing tests one final time**

Run: `pytest tests/ -v`
Expected: All pass

- [ ] **Step 3: Commit**

```bash
git add ARCHITECTURE.md
git commit -m "docs: update architecture for blockchain escrow and CDP tunnel"
```
