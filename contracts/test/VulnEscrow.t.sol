// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/VulnEscrow.sol";

contract VulnEscrowTest is Test {
    VulnEscrow escrow;

    address buyer    = address(0xBEEF);
    address seller   = address(0xCAFE);
    address operator = address(0xDEAD);
    address stranger = address(0xBAD);

    uint256 constant BUDGET  = 1 ether;
    uint256 constant RESERVE = 0.1 ether;
    uint256 constant ONE_DAY = 1 days;

    // Decay factor: 85% (850000000000000000)
    uint256 constant DECAY_85 = 85e16;
    // Full (no decay)
    uint256 constant DECAY_100 = 1e18;

    function _deploy() internal returns (VulnEscrow) {
        vm.prank(buyer);
        return new VulnEscrow{value: BUDGET}(
            buyer,
            seller,
            operator,
            RESERVE,
            block.timestamp + ONE_DAY,
            block.timestamp - 30 days, // discovered 30 days ago
            90,                         // 90 day embargo
            true                        // exclusive
        );
    }

    function setUp() public {
        // Warp to a realistic timestamp so discoveryTimestamp doesn't underflow
        vm.warp(1_700_000_000);
        vm.deal(buyer, 10 ether);
        escrow = _deploy();
    }

    // ── Constructor ──

    function test_constructor_state() public view {
        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Funded));
        assertEq(escrow.seller(), seller);
        assertEq(escrow.buyer(), buyer);
        assertEq(escrow.operator(), operator);
        assertEq(escrow.budgetCap(), BUDGET);
        assertEq(escrow.reservePrice(), RESERVE);
        assertTrue(escrow.isExclusive());
        assertTrue(escrow.isEmbargoActive());
    }

    function test_constructor_reverts_zero_value() public {
        vm.expectRevert("Must fund escrow");
        new VulnEscrow(buyer, seller, operator, 0, block.timestamp + 1, 0, 90, true);
    }

    function test_constructor_reverts_reserve_exceeds() public {
        vm.expectRevert("Reserve exceeds budget");
        new VulnEscrow{value: 0.1 ether}(buyer, seller, operator, 1 ether, block.timestamp + 1, 0, 90, true);
    }

    // ── submitOutcome ──

    function test_submit_outcome_with_decay() public {
        uint256 rawPrice = 0.5 ether;
        bytes32 attHash = keccak256("test");

        vm.prank(operator);
        escrow.submitOutcome(rawPrice, attHash, DECAY_85);

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Evaluated));
        assertEq(escrow.finalPrice(), rawPrice);
        assertEq(escrow.decayNumerator(), DECAY_85);
        // 0.5 ether * 85% = 0.425 ether
        assertEq(escrow.decayAdjustedPrice(), (rawPrice * DECAY_85) / 1e18);
        assertEq(escrow.attestationHash(), attHash);
    }

    function test_submit_outcome_full_decay() public {
        uint256 rawPrice = 0.5 ether;
        bytes32 attHash = keccak256("test");

        vm.prank(operator);
        escrow.submitOutcome(rawPrice, attHash, DECAY_100);

        assertEq(escrow.decayAdjustedPrice(), rawPrice);
    }

    function test_submit_reverts_decay_over_one() public {
        vm.prank(operator);
        vm.expectRevert("Decay numerator exceeds 1.0");
        escrow.submitOutcome(0.5 ether, keccak256("x"), 2e18);
    }

    function test_submit_reverts_decay_zero() public {
        vm.prank(operator);
        vm.expectRevert("Decay numerator must be positive");
        escrow.submitOutcome(0.5 ether, keccak256("x"), 0);
    }

    function test_submit_reverts_adjusted_exceeds_budget() public {
        vm.prank(operator);
        // rawPrice = 2 ether with 100% decay = 2 ether > 1 ether budget
        vm.expectRevert("Adjusted price exceeds budget");
        escrow.submitOutcome(2 ether, keccak256("x"), DECAY_100);
    }

    function test_submit_reverts_adjusted_below_reserve() public {
        vm.prank(operator);
        // rawPrice = 0.01 ether with 85% decay = 0.0085 ether < 0.1 ether reserve
        vm.expectRevert("Adjusted price below reserve");
        escrow.submitOutcome(0.01 ether, keccak256("x"), DECAY_85);
    }

    function test_submit_reverts_not_operator() public {
        vm.prank(stranger);
        vm.expectRevert("Only operator");
        escrow.submitOutcome(0.5 ether, keccak256("x"), DECAY_85);
    }

    function test_submit_reverts_wrong_state() public {
        // Submit once
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("x"), DECAY_85);
        // Try again in Evaluated state
        vm.prank(operator);
        vm.expectRevert("Wrong state");
        escrow.submitOutcome(0.5 ether, keccak256("x"), DECAY_85);
    }

    // ── acceptDeal ──

    function test_accept_pays_decay_adjusted() public {
        uint256 rawPrice = 0.5 ether;
        vm.prank(operator);
        escrow.submitOutcome(rawPrice, keccak256("x"), DECAY_85);

        uint256 adjusted = (rawPrice * DECAY_85) / 1e18; // 0.425 ether
        uint256 sellerBefore = seller.balance;
        uint256 buyerBefore = buyer.balance;

        vm.prank(seller);
        escrow.acceptDeal();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Accepted));
        assertEq(seller.balance, sellerBefore + adjusted);
        assertEq(buyer.balance, buyerBefore + (BUDGET - adjusted));
    }

    function test_accept_reverts_not_seller() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("x"), DECAY_85);

        vm.prank(stranger);
        vm.expectRevert("Only seller");
        escrow.acceptDeal();
    }

    // ── rejectDeal ──

    function test_reject_refunds_buyer() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("x"), DECAY_85);

        uint256 buyerBefore = buyer.balance;
        vm.prank(seller);
        escrow.rejectDeal();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Rejected));
        assertEq(buyer.balance, buyerBefore + BUDGET);
    }

    // ── reportPatch ──

    function test_report_patch_refunds_buyer() public {
        uint256 buyerBefore = buyer.balance;

        vm.prank(operator);
        escrow.reportPatch();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.PatchRefunded));
        assertTrue(escrow.isPatchedBeforeSettlement());
        assertEq(buyer.balance, buyerBefore + BUDGET);
    }

    function test_report_patch_reverts_not_operator() public {
        vm.prank(stranger);
        vm.expectRevert("Only operator");
        escrow.reportPatch();
    }

    function test_report_patch_reverts_wrong_state() public {
        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, keccak256("x"), DECAY_85);
        // Now in Evaluated, not Funded
        vm.prank(operator);
        vm.expectRevert("Wrong state");
        escrow.reportPatch();
    }

    // ── claimExpired ──

    function test_claim_expired() public {
        vm.warp(block.timestamp + 2 days);
        uint256 buyerBefore = buyer.balance;

        escrow.claimExpired();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Expired));
        assertEq(buyer.balance, buyerBefore + BUDGET);
    }

    function test_claim_expired_reverts_not_expired() public {
        vm.expectRevert("Not expired");
        escrow.claimExpired();
    }

    // ── verifyAttestation ──

    function test_verify_attestation() public {
        bytes32 pcr0 = bytes32(uint256(1));
        bytes32 nonce = bytes32(uint256(2));
        bytes32 outcome = bytes32(uint256(3));
        bytes32 attHash = keccak256(abi.encodePacked(pcr0, nonce, outcome));

        vm.prank(operator);
        escrow.submitOutcome(0.5 ether, attHash, DECAY_85);

        assertTrue(escrow.verifyAttestation(pcr0, nonce, outcome));
        assertFalse(escrow.verifyAttestation(pcr0, nonce, bytes32(uint256(999))));
    }

    // ── Embargo ──

    function test_embargo_active_initially() public view {
        assertTrue(escrow.isEmbargoActive());
    }

    function test_embargo_expires() public {
        vm.warp(block.timestamp + 91 days);
        assertFalse(escrow.isEmbargoActive());
    }

    // ── Fuzz ──

    function testFuzz_decay_adjusted_price(uint256 rawPrice, uint256 decay) public {
        rawPrice = bound(rawPrice, RESERVE, BUDGET);
        decay = bound(decay, 1, 1e18);

        uint256 adjusted = (rawPrice * decay) / 1e18;
        // Only submit if adjusted is in valid range
        if (adjusted >= RESERVE && adjusted <= BUDGET) {
            vm.prank(operator);
            escrow.submitOutcome(rawPrice, keccak256("fuzz"), decay);
            assertEq(escrow.decayAdjustedPrice(), adjusted);
        }
    }
}
