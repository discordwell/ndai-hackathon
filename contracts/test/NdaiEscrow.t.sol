// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/NdaiEscrow.sol";

contract MaliciousSeller {
    NdaiEscrow public escrow;
    uint256 public attackCount;

    // escrow address is set after construction via setEscrow
    function setEscrow(address payable _escrow) external {
        escrow = NdaiEscrow(_escrow);
    }

    function attack() external {
        escrow.acceptDeal();
    }

    receive() external payable {
        attackCount++;
        if (attackCount < 3) {
            // Attempt reentrant call — should revert due to ReentrancyGuard
            escrow.acceptDeal();
        }
    }
}

/// @dev Deploys MaliciousSeller and NdaiEscrow atomically so the escrow
///      constructor can receive the attacker's address as `seller`.
contract ReentrancyAttackSetup {
    MaliciousSeller public attacker;
    NdaiEscrow public escrow;

    function deploy(
        address _operator,
        uint256 _reserve,
        uint256 _deadline
    ) external payable {
        attacker = new MaliciousSeller();
        escrow = new NdaiEscrow{value: msg.value}(
            address(attacker),
            _operator,
            _reserve,
            _deadline
        );
        attacker.setEscrow(payable(address(escrow)));
    }
}

contract NdaiEscrowTest is Test {
    NdaiEscrow escrow;

    address buyer   = address(0xBEEF);
    address seller  = address(0xCAFE);
    address operator = address(0xDEAD);
    address stranger = address(0xBAD);

    uint256 constant BUDGET     = 1 ether;
    uint256 constant RESERVE    = 0.1 ether;
    uint256 constant ONE_DAY    = 1 days;

    function _deploy() internal returns (NdaiEscrow) {
        vm.prank(buyer);
        return new NdaiEscrow{value: BUDGET}(
            seller,
            operator,
            RESERVE,
            block.timestamp + ONE_DAY
        );
    }

    function setUp() public {
        vm.deal(buyer, 10 ether);
        escrow = _deploy();
    }

    // ------------------------------------------------------------------ //
    //  Construction / initial state                                        //
    // ------------------------------------------------------------------ //

    function test_InitialState() public view {
        assertEq(escrow.seller(),       seller);
        assertEq(escrow.buyer(),        buyer);
        assertEq(escrow.operator(),     operator);
        assertEq(escrow.reservePrice(), RESERVE);
        assertEq(escrow.budgetCap(),    BUDGET);
        assertEq(escrow.deadline(),     block.timestamp + ONE_DAY);
        assertEq(uint(escrow.state()),  uint(NdaiEscrow.State.Funded));
        assertEq(address(escrow).balance, BUDGET);
    }

    function test_Constructor_RevertZeroSeller() public {
        vm.prank(buyer);
        vm.expectRevert("Invalid seller");
        new NdaiEscrow{value: BUDGET}(address(0), operator, RESERVE, block.timestamp + ONE_DAY);
    }

    function test_Constructor_RevertZeroOperator() public {
        vm.prank(buyer);
        vm.expectRevert("Invalid operator");
        new NdaiEscrow{value: BUDGET}(seller, address(0), RESERVE, block.timestamp + ONE_DAY);
    }

    function test_Constructor_RevertNoFunds() public {
        vm.prank(buyer);
        vm.expectRevert("Must fund escrow");
        new NdaiEscrow{value: 0}(seller, operator, 0, block.timestamp + ONE_DAY);
    }

    function test_Constructor_RevertReserveExceedsBudget() public {
        vm.prank(buyer);
        vm.expectRevert("Reserve exceeds budget");
        new NdaiEscrow{value: BUDGET}(seller, operator, BUDGET + 1, block.timestamp + ONE_DAY);
    }

    function test_Constructor_RevertDeadlineInPast() public {
        vm.prank(buyer);
        vm.expectRevert("Deadline in past");
        new NdaiEscrow{value: BUDGET}(seller, operator, RESERVE, block.timestamp - 1);
    }

    // ------------------------------------------------------------------ //
    //  submitOutcome                                                       //
    // ------------------------------------------------------------------ //

    function test_SubmitOutcome_SetsEvaluatedState() public {
        bytes32 hash = keccak256("test");
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, hash);

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Evaluated));
        assertEq(escrow.finalPrice(), 0.5 ether);
        assertEq(escrow.attestationHash(), hash);
    }

    function test_SubmitOutcome_EmitsEvent() public {
        bytes32 hash = keccak256("attest");
        vm.prank(operator);
        vm.expectEmit(true, true, true, true);
        emit NdaiEscrow.OutcomeSubmitted(0.5 ether, hash);
        escrow.submitOutcome(0.5 ether, hash);
    }

    function test_SubmitOutcome_RevertNotOperator() public {
        vm.prank(stranger);
        vm.expectRevert("Only operator");
        escrow.submitOutcome(0.5 ether, bytes32(0));
    }

    function test_SubmitOutcome_RevertPriceExceedsBudgetCap() public {
        vm.prank(operator);
        vm.expectRevert("Price exceeds budget cap");
        escrow.submitOutcome(BUDGET + 1, bytes32(0));
    }

    function test_SubmitOutcome_RevertPriceBelowReserve() public {
        vm.prank(operator);
        vm.expectRevert("Price below reserve");
        escrow.submitOutcome(RESERVE - 1, bytes32(0));
    }

    function test_SubmitOutcome_RevertWrongState() public {
        // Move to Evaluated
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, bytes32(0));
        // Try again — should fail (not in Funded state)
        vm.prank(operator);
        vm.expectRevert("Wrong state");
        escrow.submitOutcome(0.5 ether, bytes32(0));
    }

    // ------------------------------------------------------------------ //
    //  acceptDeal                                                          //
    // ------------------------------------------------------------------ //

    function _submitOutcome(uint256 price) internal {
        vm.prank(operator);
        escrow.submitOutcome(price, keccak256("hash"));
    }

    function test_AcceptDeal_PaysSeller_RefundsBuyer() public {
        uint256 price = 0.6 ether;
        _submitOutcome(price);

        uint256 sellerBefore = seller.balance;
        uint256 buyerBefore  = buyer.balance;

        vm.prank(seller);
        escrow.acceptDeal();

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Accepted));
        assertEq(seller.balance, sellerBefore + price);
        assertEq(buyer.balance,  buyerBefore  + (BUDGET - price));
        assertEq(address(escrow).balance, 0);
    }

    function test_AcceptDeal_FullBudgetNoRefund() public {
        _submitOutcome(BUDGET);

        uint256 sellerBefore = seller.balance;
        uint256 buyerBefore  = buyer.balance;

        vm.prank(seller);
        escrow.acceptDeal();

        assertEq(seller.balance, sellerBefore + BUDGET);
        assertEq(buyer.balance,  buyerBefore); // no refund
    }

    function test_AcceptDeal_EmitsEvent() public {
        uint256 price = 0.7 ether;
        _submitOutcome(price);

        vm.prank(seller);
        vm.expectEmit(true, true, true, true);
        emit NdaiEscrow.DealAccepted(price, BUDGET - price);
        escrow.acceptDeal();
    }

    function test_AcceptDeal_RevertNotSeller() public {
        _submitOutcome(0.5 ether);
        vm.prank(stranger);
        vm.expectRevert("Only seller");
        escrow.acceptDeal();
    }

    function test_AcceptDeal_RevertNotEvaluated() public {
        // Still in Funded state
        vm.prank(seller);
        vm.expectRevert("Wrong state");
        escrow.acceptDeal();
    }

    function test_AcceptDeal_RevertDoubleAccept() public {
        _submitOutcome(0.5 ether);
        vm.prank(seller);
        escrow.acceptDeal();
        // Second accept must revert (state is Accepted, not Evaluated)
        vm.prank(seller);
        vm.expectRevert("Wrong state");
        escrow.acceptDeal();
    }

    // ------------------------------------------------------------------ //
    //  rejectDeal                                                          //
    // ------------------------------------------------------------------ //

    function test_RejectDeal_RefundsBuyer() public {
        _submitOutcome(0.5 ether);

        uint256 buyerBefore = buyer.balance;

        vm.prank(seller);
        escrow.rejectDeal();

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Rejected));
        assertEq(buyer.balance, buyerBefore + BUDGET);
        assertEq(address(escrow).balance, 0);
    }

    function test_RejectDeal_EmitsEvent() public {
        _submitOutcome(0.5 ether);

        vm.prank(seller);
        vm.expectEmit(true, true, true, true);
        emit NdaiEscrow.DealRejected(BUDGET);
        escrow.rejectDeal();
    }

    function test_RejectDeal_RevertNotSeller() public {
        _submitOutcome(0.5 ether);
        vm.prank(stranger);
        vm.expectRevert("Only seller");
        escrow.rejectDeal();
    }

    function test_RejectDeal_RevertNotEvaluated() public {
        // Funded state — not yet evaluated
        vm.prank(seller);
        vm.expectRevert("Wrong state");
        escrow.rejectDeal();
    }

    // ------------------------------------------------------------------ //
    //  claimExpired                                                        //
    // ------------------------------------------------------------------ //

    function test_ClaimExpired_FromFunded() public {
        vm.warp(escrow.deadline() + 1);

        uint256 buyerBefore = buyer.balance;
        escrow.claimExpired(); // anyone can call

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Expired));
        assertEq(buyer.balance, buyerBefore + BUDGET);
        assertEq(address(escrow).balance, 0);
    }

    function test_ClaimExpired_FromEvaluated() public {
        _submitOutcome(0.5 ether);
        vm.warp(escrow.deadline() + 1);

        uint256 buyerBefore = buyer.balance;
        escrow.claimExpired();

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Expired));
        assertEq(buyer.balance, buyerBefore + BUDGET);
    }

    function test_ClaimExpired_EmitsEvent() public {
        vm.warp(escrow.deadline() + 1);
        vm.expectEmit(true, true, true, true);
        emit NdaiEscrow.DealExpired(BUDGET);
        escrow.claimExpired();
    }

    function test_ClaimExpired_RevertBeforeDeadline() public {
        // Deadline has not passed yet
        vm.expectRevert("Not expired");
        escrow.claimExpired();
    }

    function test_ClaimExpired_RevertWrongState_AfterAccept() public {
        _submitOutcome(0.5 ether);
        vm.prank(seller);
        escrow.acceptDeal();

        vm.warp(escrow.deadline() + 1);
        vm.expectRevert("Wrong state");
        escrow.claimExpired();
    }

    // ------------------------------------------------------------------ //
    //  verifyAttestation                                                   //
    // ------------------------------------------------------------------ //

    function test_VerifyAttestation_CorrectHash() public {
        bytes32 pcr0    = keccak256("pcr0");
        bytes32 nonce   = keccak256("nonce");
        bytes32 outcome = keccak256("outcome");
        bytes32 hash    = keccak256(abi.encodePacked(pcr0, nonce, outcome));

        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, hash);

        assertTrue(escrow.verifyAttestation(pcr0, nonce, outcome));
    }

    function test_VerifyAttestation_WrongHash() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("correct"));

        assertFalse(escrow.verifyAttestation(bytes32(0), bytes32(0), bytes32(0)));
    }

    // ------------------------------------------------------------------ //
    //  Fuzz: any price in [reservePrice, budgetCap] should succeed         //
    // ------------------------------------------------------------------ //

    function testFuzz_SubmitOutcome_ValidPrice(uint256 price) public {
        price = bound(price, RESERVE, BUDGET);

        vm.prank(operator);
        escrow.submitOutcome(price, keccak256("fuzz"));

        assertEq(uint(escrow.state()), uint(NdaiEscrow.State.Evaluated));
        assertEq(escrow.finalPrice(), price);
    }

    // ------------------------------------------------------------------ //
    //  Reentrancy attack                                                   //
    // ------------------------------------------------------------------ //

    function test_Reentrancy_AcceptDeal_Reverts() public {
        uint256 budget = 1 ether;
        uint256 reserve = 0.1 ether;

        // Deploy attacker + escrow atomically so the escrow knows the attacker's address
        ReentrancyAttackSetup setup = new ReentrancyAttackSetup();
        vm.deal(address(setup), budget);
        setup.deploy{value: budget}(operator, reserve, block.timestamp + ONE_DAY);

        MaliciousSeller attacker = setup.attacker();
        NdaiEscrow attackEscrow  = setup.escrow();

        // Move to Evaluated state
        vm.prank(operator);
        attackEscrow.submitOutcome(0.5 ether, keccak256("attest"));

        // Launch attack — should revert due to ReentrancyGuard
        vm.expectRevert();
        attacker.attack();
    }
}
