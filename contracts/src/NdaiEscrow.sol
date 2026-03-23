// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title NdaiEscrow — Per-deal escrow for NDAI bilateral Nash bargaining
/// @author NDAI (arxiv:2502.07924)
/// @notice Holds buyer funds during TEE-mediated negotiation. The operator (TEE enclave)
///   submits the equilibrium price; the seller accepts or rejects; funds settle accordingly.
/// @dev State machine: Created → Funded → Evaluated → Accepted | Rejected | Expired.
///   The escrow is created in the Funded state (constructor requires msg.value > 0).
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

    /// @notice Deploy a new escrow. Buyer sends ETH as the budget cap.
    /// @param _buyer Address of the buyer (investor)
    /// @param _seller Address of the seller (inventor)
    /// @param _operator Address of the TEE operator that submits the negotiation outcome
    /// @param _reservePrice Minimum price the seller will accept (in wei)
    /// @param _deadline Unix timestamp after which the deal expires and buyer is refunded
    constructor(
        address _buyer,
        address _seller,
        address _operator,
        uint256 _reservePrice,
        uint256 _deadline
    ) payable {
        require(msg.value > 0, "Must fund escrow");
        require(_buyer != address(0), "Invalid buyer");
        require(_seller != address(0), "Invalid seller");
        require(_operator != address(0), "Invalid operator");
        require(_reservePrice <= msg.value, "Reserve exceeds budget");
        require(_deadline > block.timestamp, "Deadline in past");

        seller = _seller;
        buyer = _buyer;
        operator = _operator;
        reservePrice = _reservePrice;
        budgetCap = msg.value;
        deadline = _deadline;
        state = State.Funded;
    }

    /// @notice Operator submits the bilateral Nash equilibrium price from the TEE negotiation.
    /// @param _finalPrice The agreed-upon price (in wei), must be within [reservePrice, budgetCap]
    /// @param _attestationHash Hash of the enclave attestation document for on-chain verification
    function submitOutcome(uint256 _finalPrice, bytes32 _attestationHash)
        external onlyOperator inState(State.Funded)
    {
        require(_finalPrice <= budgetCap, "Price exceeds budget cap");
        require(_finalPrice >= reservePrice, "Price below reserve");
        finalPrice = _finalPrice;
        attestationHash = _attestationHash;
        state = State.Evaluated;
        emit OutcomeSubmitted(_finalPrice, _attestationHash);
    }

    /// @notice Seller accepts the deal. Seller receives finalPrice, buyer receives remainder.
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

    /// @notice Seller rejects the deal. Full balance refunded to buyer.
    function rejectDeal() external onlySeller inState(State.Evaluated) nonReentrant {
        state = State.Rejected;
        uint256 refund = address(this).balance;
        emit DealRejected(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Anyone can trigger expiration after the deadline. Full balance refunded to buyer.
    function claimExpired() external nonReentrant {
        require(block.timestamp > deadline, "Not expired");
        require(state == State.Funded || state == State.Evaluated, "Wrong state");
        state = State.Expired;
        uint256 refund = address(this).balance;
        emit DealExpired(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Verify attestation by comparing stored hash against computed hash.
    /// @param pcr0 PCR0 value from the enclave image
    /// @param nonce Freshness nonce used during attestation
    /// @param outcome Hash of the negotiation outcome
    /// @return True if the attestation matches
    function verifyAttestation(bytes32 pcr0, bytes32 nonce, bytes32 outcome)
        external view returns (bool)
    {
        return attestationHash == keccak256(abi.encodePacked(pcr0, nonce, outcome));
    }
}
