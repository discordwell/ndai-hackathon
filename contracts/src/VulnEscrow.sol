// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./PCR0Registry.sol";

/// @title VulnEscrow — Escrow for zero-day vulnerability marketplace deals
/// @notice Seller lists a price, buyer pays it, platform takes 10%.
///         The TEE verifies the exploit is real before the seller can accept.
///
///         Anti-self-proof: verification is only accepted if the enclave's PCR0
///         matches either (a) a registered PCR0 in the PCR0Registry (with public
///         build spec), or (b) a PCR0 the buyer specified directly. The operator
///         cannot prove zero-days on a rigged target because the build spec is
///         public and the PCR0 is deterministic.
contract VulnEscrow is ReentrancyGuard {
    enum State { Created, Funded, Verified, Accepted, Rejected, Expired, PatchRefunded }
    enum VerificationMode { Registry, BuyerChallenge }

    address public immutable seller;
    address public immutable buyer;
    address public immutable operator;   // TEE operator — submits verification result
    address public immutable platform;   // Platform operator — receives 10% fee
    uint256 public immutable price;      // Seller's asking price
    uint256 public immutable deadline;
    uint256 public constant PLATFORM_FEE_BPS = 1000; // 10% in basis points

    // Vuln metadata
    bool    public immutable isExclusive;

    // Anti-self-proof: PCR0 verification
    PCR0Registry public immutable pcr0Registry;
    VerificationMode public immutable verificationMode;
    // Buyer-challenge mode: buyer specifies the exact PCR0 they expect
    bytes32 public immutable challengePCR0High;
    bytes16 public immutable challengePCR0Low;

    // Set by operator after TEE verification
    bytes32 public attestationHash;
    bytes32 public verifiedPCR0High;
    bytes16 public verifiedPCR0Low;
    State   public state;
    bool    public isPatchedBeforeSettlement;

    // Sealed delivery commitments (exploit transfer)
    bytes32 public deliveryHash;     // SHA-256(encrypted_exploit)
    bytes32 public keyCommitment;    // SHA-256(encrypted_delivery_key)

    event Verified(bytes32 attestationHash, bytes32 deliveryHash, bytes32 keyCommitment, bytes32 pcr0High, bytes16 pcr0Low);
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
    /// @param _pcr0Registry Address of the PCR0Registry contract
    /// @param _mode        Registry (check against PCR0Registry) or BuyerChallenge (buyer specifies PCR0)
    /// @param _challengePCR0High First 32 bytes of buyer's expected PCR0 (only used in BuyerChallenge mode)
    /// @param _challengePCR0Low  Last 16 bytes of buyer's expected PCR0 (only used in BuyerChallenge mode)
    constructor(
        address _buyer,
        address _seller,
        address _operator,
        address _platform,
        uint256 _price,
        uint256 _deadline,
        bool    _isExclusive,
        address _pcr0Registry,
        VerificationMode _mode,
        bytes32 _challengePCR0High,
        bytes16 _challengePCR0Low
    ) payable {
        require(msg.value >= _price, "Insufficient funding");
        require(msg.value > 0, "Must fund escrow");
        require(_buyer    != address(0), "Invalid buyer");
        require(_seller   != address(0), "Invalid seller");
        require(_operator != address(0), "Invalid operator");
        require(_platform != address(0), "Invalid platform");
        require(_price > 0, "Price must be positive");
        require(_deadline > block.timestamp, "Deadline in past");
        require(_pcr0Registry != address(0), "Invalid registry");

        if (_mode == VerificationMode.BuyerChallenge) {
            require(
                _challengePCR0High != bytes32(0) || _challengePCR0Low != bytes16(0),
                "Challenge PCR0 required"
            );
        }

        seller   = _seller;
        buyer    = _buyer;
        operator = _operator;
        platform = _platform;
        price    = _price;
        deadline = _deadline;
        isExclusive = _isExclusive;
        pcr0Registry = PCR0Registry(_pcr0Registry);
        verificationMode = _mode;
        challengePCR0High = _challengePCR0High;
        challengePCR0Low = _challengePCR0Low;
        state = State.Funded;
    }

    /// @notice TEE operator submits verification result + sealed delivery commitments.
    ///         The PCR0 from the attestation must match either the registry or the
    ///         buyer's challenge value. This prevents the operator from verifying
    ///         against a rigged target.
    function submitVerification(
        bytes32 _attestationHash,
        bytes32 _deliveryHash,
        bytes32 _keyCommitment,
        bytes32 _pcr0High,
        bytes16 _pcr0Low
    ) external onlyOperator inState(State.Funded) {
        // Anti-self-proof: verify the PCR0 is legitimate
        if (verificationMode == VerificationMode.Registry) {
            (bool registered,,) = pcr0Registry.verifyPCR0(_pcr0High, _pcr0Low);
            require(registered, "PCR0 not in registry");
        } else {
            require(
                _pcr0High == challengePCR0High && _pcr0Low == challengePCR0Low,
                "PCR0 does not match buyer challenge"
            );
        }

        attestationHash = _attestationHash;
        deliveryHash    = _deliveryHash;
        keyCommitment   = _keyCommitment;
        verifiedPCR0High = _pcr0High;
        verifiedPCR0Low  = _pcr0Low;
        state = State.Verified;
        emit Verified(_attestationHash, _deliveryHash, _keyCommitment, _pcr0High, _pcr0Low);
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

    /// @notice Get the PCR0 that was used for verification, so anyone can
    ///         look up the build spec in the registry and verify independently.
    function getVerifiedPCR0() external view returns (bytes32, bytes16) {
        return (verifiedPCR0High, verifiedPCR0Low);
    }
}
