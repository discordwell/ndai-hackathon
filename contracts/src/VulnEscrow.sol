// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VulnEscrow — Escrow for zero-day vulnerability marketplace deals
/// @notice Extends the NdaiEscrow pattern with time-decay pricing, patch oracle,
///         and embargo tracking for vulnerability transactions.
contract VulnEscrow is ReentrancyGuard {
    enum State { Created, Funded, Evaluated, Accepted, Rejected, Expired, PatchRefunded }

    address public immutable seller;
    address public immutable buyer;
    address public immutable operator;
    uint256 public immutable reservePrice;
    uint256 public immutable budgetCap;
    uint256 public immutable deadline;

    // Vuln-specific immutables
    uint256 public immutable discoveryTimestamp;
    uint256 public immutable embargoEndTimestamp;
    bool    public immutable isExclusive;

    // Mutable state
    uint256 public finalPrice;
    uint256 public decayAdjustedPrice;
    uint256 public decayNumerator;   // Decay factor * 1e18
    bytes32 public attestationHash;
    State   public state;
    bool    public isPatchedBeforeSettlement;

    event OutcomeSubmitted(uint256 finalPrice, uint256 decayAdjustedPrice, bytes32 attestationHash);
    event DealAccepted(uint256 sellerPayout, uint256 buyerRefund);
    event DealRejected(uint256 buyerRefund);
    event DealExpired(uint256 buyerRefund);
    event PatchDetected(uint256 buyerRefund);

    modifier onlyOperator() { require(msg.sender == operator, "Only operator"); _; }
    modifier onlySeller()   { require(msg.sender == seller,   "Only seller");   _; }
    modifier inState(State s) { require(state == s, "Wrong state"); _; }

    constructor(
        address _buyer,
        address _seller,
        address _operator,
        uint256 _reservePrice,
        uint256 _deadline,
        uint256 _discoveryTimestamp,
        uint256 _embargoDays,
        bool    _isExclusive
    ) payable {
        require(msg.value > 0, "Must fund escrow");
        require(_buyer    != address(0), "Invalid buyer");
        require(_seller   != address(0), "Invalid seller");
        require(_operator != address(0), "Invalid operator");
        require(_reservePrice <= msg.value, "Reserve exceeds budget");
        require(_deadline > block.timestamp, "Deadline in past");

        seller   = _seller;
        buyer    = _buyer;
        operator = _operator;
        reservePrice = _reservePrice;
        budgetCap    = msg.value;
        deadline     = _deadline;

        discoveryTimestamp  = _discoveryTimestamp;
        embargoEndTimestamp = block.timestamp + (_embargoDays * 1 days);
        isExclusive = _isExclusive;
        state = State.Funded;
    }

    /// @notice Operator submits negotiation outcome with decay-adjusted pricing.
    /// @param _finalPrice     Raw Nash-bargained price (before decay)
    /// @param _attestationHash Hash from TEE attestation
    /// @param _decayNumerator  Decay factor × 1e18 (e.g., 0.85 × 1e18 = 850000000000000000)
    function submitOutcome(
        uint256 _finalPrice,
        bytes32 _attestationHash,
        uint256 _decayNumerator
    ) external onlyOperator inState(State.Funded) {
        require(_decayNumerator <= 1e18, "Decay numerator exceeds 1.0");
        require(_decayNumerator > 0, "Decay numerator must be positive");

        uint256 adjusted = (_finalPrice * _decayNumerator) / 1e18;
        require(adjusted <= budgetCap, "Adjusted price exceeds budget");
        require(adjusted >= reservePrice, "Adjusted price below reserve");

        finalPrice        = _finalPrice;
        decayNumerator    = _decayNumerator;
        decayAdjustedPrice = adjusted;
        attestationHash    = _attestationHash;
        state = State.Evaluated;

        emit OutcomeSubmitted(_finalPrice, adjusted, _attestationHash);
    }

    /// @notice Operator reports that the vulnerability has been independently patched.
    ///         Full refund to buyer.
    function reportPatch() external onlyOperator inState(State.Funded) nonReentrant {
        isPatchedBeforeSettlement = true;
        state = State.PatchRefunded;
        uint256 refund = address(this).balance;
        emit PatchDetected(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Seller accepts the deal. Pays decayAdjustedPrice to seller, refunds rest.
    function acceptDeal() external onlySeller inState(State.Evaluated) nonReentrant {
        state = State.Accepted;
        uint256 sellerPayout = decayAdjustedPrice;
        uint256 buyerRefund  = address(this).balance - sellerPayout;
        emit DealAccepted(sellerPayout, buyerRefund);
        (bool s1,) = seller.call{value: sellerPayout}("");
        require(s1, "Seller transfer failed");
        if (buyerRefund > 0) {
            (bool s2,) = buyer.call{value: buyerRefund}("");
            require(s2, "Buyer refund failed");
        }
    }

    /// @notice Seller rejects the deal. Full refund to buyer.
    function rejectDeal() external onlySeller inState(State.Evaluated) nonReentrant {
        state = State.Rejected;
        uint256 refund = address(this).balance;
        emit DealRejected(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Anyone can claim expired deal after deadline. Full refund to buyer.
    function claimExpired() external nonReentrant {
        require(block.timestamp > deadline, "Not expired");
        require(state == State.Funded || state == State.Evaluated, "Wrong state");
        state = State.Expired;
        uint256 refund = address(this).balance;
        emit DealExpired(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Verify attestation hash matches provided components.
    function verifyAttestation(bytes32 pcr0, bytes32 nonce, bytes32 outcome)
        external view returns (bool)
    {
        return attestationHash == keccak256(abi.encodePacked(pcr0, nonce, outcome));
    }

    /// @notice Check if embargo period is still active.
    function isEmbargoActive() external view returns (bool) {
        return block.timestamp < embargoEndTimestamp;
    }
}
