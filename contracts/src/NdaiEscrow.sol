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
        require(state == State.Funded || state == State.Evaluated, "Wrong state");
        state = State.Expired;
        uint256 refund = address(this).balance;
        emit DealExpired(refund);
        (bool ok,) = buyer.call{value: refund}("");
        require(ok, "Refund failed");
    }

    function verifyAttestation(bytes32 pcr0, bytes32 nonce, bytes32 outcome)
        external view returns (bool)
    {
        return attestationHash == keccak256(abi.encodePacked(pcr0, nonce, outcome));
    }
}
