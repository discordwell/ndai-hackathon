// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/// @title VulnEscrow — Escrow for zero-day vulnerability marketplace deals
/// @notice Seller lists a price, buyer pays it, platform takes 10%.
///         The TEE verifies the exploit is real before the seller can accept.
contract VulnEscrow is ReentrancyGuard {
    enum State { Created, Funded, Verified, Accepted, Rejected, Expired, PatchRefunded }

    address public immutable seller;
    address public immutable buyer;
    address public immutable operator;   // TEE operator — submits verification result
    address public immutable platform;   // Platform operator — receives 10% fee
    uint256 public immutable price;      // Seller's asking price
    uint256 public immutable deadline;
    uint256 public constant PLATFORM_FEE_BPS = 1000; // 10% in basis points

    // Vuln metadata
    bool    public immutable isExclusive;

    // Set by operator after TEE verification
    bytes32 public attestationHash;
    State   public state;
    bool    public isPatchedBeforeSettlement;

    // Sealed delivery commitments (exploit transfer)
    bytes32 public deliveryHash;     // SHA-256(encrypted_exploit)
    bytes32 public keyCommitment;    // SHA-256(encrypted_delivery_key)

    event Verified(bytes32 attestationHash, bytes32 deliveryHash, bytes32 keyCommitment);
    event DealAccepted(uint256 sellerPayout, uint256 platformFee, uint256 buyerRefund);
    event DealRejected(uint256 buyerRefund);
    event DealExpired(uint256 buyerRefund);
    event PatchDetected(uint256 buyerRefund);

    modifier onlyOperator() { require(msg.sender == operator, "Only operator"); _; }
    modifier onlySeller()   { require(msg.sender == seller,   "Only seller");   _; }
    modifier inState(State s) { require(state == s, "Wrong state"); _; }

    /// @param _buyer       Buyer address (funds the escrow)
    /// @param _seller      Vulnerability researcher
    /// @param _operator    TEE operator
    /// @param _platform    Platform fee recipient
    /// @param _price       Seller's asking price (buyer must fund at least this much)
    /// @param _deadline    Unix timestamp — deal expires after this
    /// @param _isExclusive Whether this is an exclusive deal
    constructor(
        address _buyer,
        address _seller,
        address _operator,
        address _platform,
        uint256 _price,
        uint256 _deadline,
        bool    _isExclusive
    ) payable {
        require(msg.value >= _price, "Insufficient funding");
        require(msg.value > 0, "Must fund escrow");
        require(_buyer    != address(0), "Invalid buyer");
        require(_seller   != address(0), "Invalid seller");
        require(_operator != address(0), "Invalid operator");
        require(_platform != address(0), "Invalid platform");
        require(_price > 0, "Price must be positive");
        require(_deadline > block.timestamp, "Deadline in past");

        seller   = _seller;
        buyer    = _buyer;
        operator = _operator;
        platform = _platform;
        price    = _price;
        deadline = _deadline;
        isExclusive = _isExclusive;
        state = State.Funded;
    }

    /// @notice TEE operator submits verification result + sealed delivery commitments.
    ///         This proves the exploit is real (capability oracle passed inside the enclave).
    function submitVerification(
        bytes32 _attestationHash,
        bytes32 _deliveryHash,
        bytes32 _keyCommitment
    ) external onlyOperator inState(State.Funded) {
        attestationHash = _attestationHash;
        deliveryHash    = _deliveryHash;
        keyCommitment   = _keyCommitment;
        state = State.Verified;
        emit Verified(_attestationHash, _deliveryHash, _keyCommitment);
    }

    /// @notice Operator reports the vuln was independently patched. Full refund.
    function reportPatch() external onlyOperator inState(State.Funded) nonReentrant {
        isPatchedBeforeSettlement = true;
        state = State.PatchRefunded;
        uint256 refund = address(this).balance;
        emit PatchDetected(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Seller accepts the deal. Payment splits: 90% seller, 10% platform.
    ///         Any excess funding is refunded to the buyer.
    function acceptDeal() external onlySeller inState(State.Verified) nonReentrant {
        state = State.Accepted;
        uint256 fee = (price * PLATFORM_FEE_BPS) / 10000;
        uint256 sellerPayout = price - fee;
        uint256 buyerRefund  = address(this).balance - price;
        emit DealAccepted(sellerPayout, fee, buyerRefund);
        (bool s1,) = seller.call{value: sellerPayout}("");
        require(s1, "Seller transfer failed");
        (bool s2,) = platform.call{value: fee}("");
        require(s2, "Platform fee transfer failed");
        if (buyerRefund > 0) {
            (bool s3,) = buyer.call{value: buyerRefund}("");
            require(s3, "Buyer refund failed");
        }
    }

    /// @notice Seller rejects the deal. Full refund to buyer.
    function rejectDeal() external onlySeller inState(State.Verified) nonReentrant {
        state = State.Rejected;
        uint256 refund = address(this).balance;
        emit DealRejected(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Anyone can trigger refund after deadline.
    function claimExpired() external nonReentrant {
        require(block.timestamp > deadline, "Not expired");
        require(state == State.Funded || state == State.Verified, "Wrong state");
        state = State.Expired;
        uint256 refund = address(this).balance;
        emit DealExpired(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    /// @notice Verify attestation hash.
    function verifyAttestation(bytes32 pcr0, bytes32 nonce, bytes32 outcome)
        external view returns (bool)
    {
        return attestationHash == keccak256(abi.encodePacked(pcr0, nonce, outcome));
    }

    /// @notice Verify delivery commitments.
    function verifyDelivery(bytes32 _deliveryHash, bytes32 _keyCommitment)
        external view returns (bool)
    {
        return deliveryHash == _deliveryHash && keyCommitment == _keyCommitment;
    }
}
