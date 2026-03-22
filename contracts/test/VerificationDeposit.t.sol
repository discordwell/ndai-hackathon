// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/VerificationDeposit.sol";

contract VerificationDepositTest is Test {
    VerificationDeposit vd;

    address operator = address(0xDEAD);
    address platform = address(0xFEE);
    address seller   = address(0xCAFE);
    address stranger = address(0xBAD);

    bytes32 constant PROPOSAL_1 = keccak256("proposal-1");
    bytes32 constant PROPOSAL_2 = keccak256("proposal-2");

    function setUp() public {
        vd = new VerificationDeposit(operator, platform);
        vm.deal(seller, 10 ether);
        vm.deal(stranger, 10 ether);
    }

    // ── 1. deposit and refund (happy path) ──

    function test_deposit_and_refund() public {
        // Seller deposits
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        (address depSeller, uint256 depAmount, bool settled) = vd.deposits(PROPOSAL_1);
        assertEq(depSeller, seller);
        assertEq(depAmount, 0.04 ether);
        assertFalse(settled);

        // Operator refunds
        uint256 sellerBefore = seller.balance;
        vm.prank(operator);
        vd.refund(PROPOSAL_1);

        (, , bool settledAfter) = vd.deposits(PROPOSAL_1);
        assertTrue(settledAfter);
        assertEq(seller.balance, sellerBefore + 0.04 ether);
    }

    // ── 2. deposit and forfeit ──

    function test_deposit_and_forfeit() public {
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        uint256 platformBalBefore = vd.platformBalance();

        vm.prank(operator);
        vd.forfeit(PROPOSAL_1);

        (, , bool settled) = vd.deposits(PROPOSAL_1);
        assertTrue(settled);
        assertEq(vd.platformBalance(), platformBalBefore + 0.04 ether);
    }

    // ── 3. double deposit reverts ──

    function test_double_deposit_reverts() public {
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        vm.prank(seller);
        vm.expectRevert("Already deposited");
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);
    }

    // ── 4. refund already settled reverts ──

    function test_refund_already_settled_reverts() public {
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        vm.prank(operator);
        vd.refund(PROPOSAL_1);

        vm.prank(operator);
        vm.expectRevert("Already settled");
        vd.refund(PROPOSAL_1);
    }

    // ── 5. only operator can refund ──

    function test_only_operator_can_refund() public {
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        vm.prank(stranger);
        vm.expectRevert("Only operator");
        vd.refund(PROPOSAL_1);
    }

    // ── 6. only operator can forfeit ──

    function test_only_operator_can_forfeit() public {
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        vm.prank(stranger);
        vm.expectRevert("Only operator");
        vd.forfeit(PROPOSAL_1);
    }

    // ── 7. badge purchase ──

    function test_badge_purchase() public {
        assertFalse(vd.hasBadge(seller));

        vm.prank(seller);
        vd.purchaseBadge{value: 0.04 ether}();

        assertTrue(vd.hasBadge(seller));
        assertEq(vd.platformBalance(), 0.04 ether);
    }

    // ── 8. badge purchase already has badge reverts ──

    function test_badge_purchase_already_has_badge_reverts() public {
        vm.prank(seller);
        vd.purchaseBadge{value: 0.04 ether}();

        vm.prank(seller);
        vm.expectRevert("Already has badge");
        vd.purchaseBadge{value: 0.04 ether}();
    }

    // ── 9. badge grant by operator ──

    function test_badge_grant_by_operator() public {
        assertFalse(vd.hasBadge(seller));

        vm.prank(operator);
        vd.grantBadge(seller);

        assertTrue(vd.hasBadge(seller));
    }

    // ── 10. platform escrow set and used ──

    function test_platform_escrow_set_and_used() public {
        bytes32 linuxKey = keccak256("linux");

        // Operator sets a higher escrow for "linux" platform
        vm.prank(operator);
        vd.setPlatformEscrow(linuxKey, 0.1 ether);

        assertEq(vd.platformEscrow(linuxKey), 0.1 ether);

        // Deposit using the linuxKey as proposalId — but platformEscrow is keyed by proposalId
        // so we use linuxKey as the proposalId to demonstrate the lookup
        vm.prank(seller);
        vm.expectRevert("Insufficient deposit");
        vd.deposit{value: 0.04 ether}(linuxKey);

        // Now deposit with sufficient amount
        vm.prank(seller);
        vd.deposit{value: 0.1 ether}(linuxKey);

        (address depSeller, uint256 depAmount, ) = vd.deposits(linuxKey);
        assertEq(depSeller, seller);
        assertEq(depAmount, 0.1 ether);
    }

    // ── 11. withdraw platform fees ──

    function test_withdraw_platform_fees() public {
        // Accumulate fees via forfeit
        vm.prank(seller);
        vd.deposit{value: 0.04 ether}(PROPOSAL_1);

        vm.prank(operator);
        vd.forfeit(PROPOSAL_1);

        // Also accumulate via badge purchase
        vm.prank(stranger);
        vd.purchaseBadge{value: 0.04 ether}();

        uint256 expectedFees = 0.08 ether;
        assertEq(vd.platformBalance(), expectedFees);

        uint256 platformBefore = platform.balance;

        vm.prank(operator);
        vd.withdrawPlatformFees();

        assertEq(platform.balance, platformBefore + expectedFees);
        assertEq(vd.platformBalance(), 0);
    }

    // ── 12. deposit insufficient amount reverts ──

    function test_deposit_insufficient_amount_reverts() public {
        vm.prank(seller);
        vm.expectRevert("Insufficient deposit");
        vd.deposit{value: 0.01 ether}(PROPOSAL_1);
    }
}
