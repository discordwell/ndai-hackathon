// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/SeriousCustomer.sol";

/// @dev Mock Chainlink aggregator for testing
contract MockAggregator {
    int256 public price;
    uint256 public updatedAt;

    constructor(int256 _price) {
        price = _price;
        updatedAt = block.timestamp;
    }

    function setPrice(int256 _price) external {
        price = _price;
        updatedAt = block.timestamp;
    }

    function setUpdatedAt(uint256 _updatedAt) external {
        updatedAt = _updatedAt;
    }

    function latestRoundData()
        external
        view
        returns (uint80, int256, uint256, uint256, uint80)
    {
        return (1, price, 0, updatedAt, 1);
    }

    function decimals() external pure returns (uint8) {
        return 8;
    }
}

contract SeriousCustomerTest is Test {
    SeriousCustomer sc;
    MockAggregator mockFeed;

    address operator = address(0xDEAD);
    address platform = address(0xFEE);
    address buyer1   = address(0xB001);
    address buyer2   = address(0xB002);
    address stranger = address(0xBAD);

    // ETH at $2,500 → 8 decimals = 250_000_000_000
    int256 constant ETH_2500 = 250_000_000_000;
    // At $2,500/ETH, $5,000 = 2 ETH
    uint256 constant TWO_ETH = 2 ether;

    function setUp() public {
        mockFeed = new MockAggregator(ETH_2500);
        sc = new SeriousCustomer(operator, platform, address(mockFeed));
        vm.deal(buyer1, 100 ether);
        vm.deal(buyer2, 100 ether);
    }

    // ── 1. deposit becomes SC ──

    function test_deposit_becomes_sc() public {
        vm.prank(buyer1);
        sc.deposit{value: TWO_ETH}();

        assertTrue(sc.isSeriousCustomer(buyer1));
        assertEq(sc.depositOf(buyer1), TWO_ETH);
        assertFalse(sc.hasBeenRefunded(buyer1));
    }

    // ── 2. deposit insufficient reverts ──

    function test_deposit_insufficient_reverts() public {
        vm.prank(buyer1);
        vm.expectRevert("Insufficient deposit");
        sc.deposit{value: 1 ether}();
    }

    // ── 3. double deposit reverts ──

    function test_deposit_already_sc_reverts() public {
        vm.prank(buyer1);
        sc.deposit{value: TWO_ETH}();

        vm.prank(buyer1);
        vm.expectRevert("Already SC");
        sc.deposit{value: TWO_ETH}();
    }

    // ── 4. refund by operator ──

    function test_refund_by_operator() public {
        vm.prank(buyer1);
        sc.deposit{value: TWO_ETH}();

        uint256 buyerBefore = buyer1.balance;

        vm.prank(operator);
        sc.refundDeposit(buyer1);

        assertTrue(sc.hasBeenRefunded(buyer1));
        assertTrue(sc.isSeriousCustomer(buyer1)); // still SC after refund
        assertEq(buyer1.balance, buyerBefore + TWO_ETH);
    }

    // ── 5. double refund reverts ──

    function test_refund_already_refunded_reverts() public {
        vm.prank(buyer1);
        sc.deposit{value: TWO_ETH}();

        vm.prank(operator);
        sc.refundDeposit(buyer1);

        vm.prank(operator);
        vm.expectRevert("Already refunded");
        sc.refundDeposit(buyer1);
    }

    // ── 6. refund non-operator reverts ──

    function test_refund_non_operator_reverts() public {
        vm.prank(buyer1);
        sc.deposit{value: TWO_ETH}();

        vm.prank(stranger);
        vm.expectRevert("Only operator");
        sc.refundDeposit(buyer1);
    }

    // ── 7. refund non-SC reverts ──

    function test_refund_non_sc_reverts() public {
        vm.prank(operator);
        vm.expectRevert("Not SC");
        sc.refundDeposit(buyer1);
    }

    // ── 8. grant by operator ──

    function test_grant_by_operator() public {
        vm.prank(operator);
        sc.grantSeriousCustomer(buyer1);

        assertTrue(sc.isSeriousCustomer(buyer1));
        assertEq(sc.depositOf(buyer1), 0); // no deposit
    }

    // ── 9. grant already SC reverts ──

    function test_grant_already_sc_reverts() public {
        vm.prank(operator);
        sc.grantSeriousCustomer(buyer1);

        vm.prank(operator);
        vm.expectRevert("Already SC");
        sc.grantSeriousCustomer(buyer1);
    }

    // ── 10. grant non-operator reverts ──

    function test_grant_non_operator_reverts() public {
        vm.prank(stranger);
        vm.expectRevert("Only operator");
        sc.grantSeriousCustomer(buyer1);
    }

    // ── 11. getMinDepositWei matches price ──

    function test_getMinDepositWei_at_2500() public view {
        uint256 minWei = sc.getMinDepositWei();
        // $5,000 / $2,500 = 2 ETH
        assertEq(minWei, TWO_ETH);
    }

    function test_getMinDepositWei_at_5000() public {
        // ETH at $5,000 → $5,000 deposit = 1 ETH
        mockFeed.setPrice(500_000_000_000);
        uint256 minWei = sc.getMinDepositWei();
        assertEq(minWei, 1 ether);
    }

    // ── 12. stale price reverts ──

    function test_stale_price_reverts() public {
        // Warp forward so we can set a past timestamp without underflow
        vm.warp(100 hours);
        mockFeed.setPrice(ETH_2500);
        mockFeed.setUpdatedAt(block.timestamp - 25 hours);

        vm.prank(buyer1);
        vm.expectRevert("Stale price");
        sc.deposit{value: TWO_ETH}();
    }

    // ── 13. invalid price reverts ──

    function test_invalid_price_reverts() public {
        mockFeed.setPrice(0);

        vm.prank(buyer1);
        vm.expectRevert("Invalid price");
        sc.deposit{value: TWO_ETH}();
    }

    // ── 14. refund granted SC (no deposit) reverts ──

    function test_refund_granted_no_deposit_reverts() public {
        vm.prank(operator);
        sc.grantSeriousCustomer(buyer1);

        vm.prank(operator);
        vm.expectRevert("No deposit to refund");
        sc.refundDeposit(buyer1);
    }

    // ── 15. deposit with excess ETH ──

    function test_deposit_excess_eth() public {
        vm.prank(buyer1);
        sc.deposit{value: 5 ether}();

        assertTrue(sc.isSeriousCustomer(buyer1));
        assertEq(sc.depositOf(buyer1), 5 ether); // stores full amount
    }

    // ── 16. events ──

    function test_deposit_emits_event() public {
        vm.prank(buyer1);
        vm.expectEmit(true, false, false, true);
        emit SeriousCustomer.SeriousCustomerDeposited(buyer1, TWO_ETH, uint256(ETH_2500));
        sc.deposit{value: TWO_ETH}();
    }

    function test_refund_emits_event() public {
        vm.prank(buyer1);
        sc.deposit{value: TWO_ETH}();

        vm.prank(operator);
        vm.expectEmit(true, false, false, true);
        emit SeriousCustomer.SeriousCustomerRefunded(buyer1, TWO_ETH);
        sc.refundDeposit(buyer1);
    }

    function test_grant_emits_event() public {
        vm.prank(operator);
        vm.expectEmit(true, false, false, false);
        emit SeriousCustomer.SeriousCustomerGranted(buyer1);
        sc.grantSeriousCustomer(buyer1);
    }
}
