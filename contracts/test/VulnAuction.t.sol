// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/VulnAuction.sol";
import "../src/VulnAuctionFactory.sol";

/// @dev Mock SeriousCustomer contract for testing
contract MockSeriousCustomer {
    mapping(address => bool) public isSeriousCustomer;

    function setStatus(address user, bool status) external {
        isSeriousCustomer[user] = status;
    }
}

contract VulnAuctionTest is Test {
    VulnAuction auction;
    VulnAuctionFactory factory;
    MockSeriousCustomer mockSC;

    address seller   = address(0xCAFE);
    address operator = address(0xDEAD);
    address platform = address(0xFEE);
    address bidder1  = address(0xB001);
    address bidder2  = address(0xB002);
    address stranger = address(0xBAD);

    uint256 constant RESERVE = 1 ether;
    uint256 constant DURATION = 1 hours;

    function setUp() public {
        mockSC = new MockSeriousCustomer();
        factory = new VulnAuctionFactory(platform, address(mockSC));

        vm.deal(seller, 10 ether);
        vm.deal(bidder1, 100 ether);
        vm.deal(bidder2, 100 ether);

        // Default: create a non-SC-only auction via factory
        vm.prank(seller);
        address auctionAddr = factory.createAuction(operator, RESERVE, DURATION, false);
        auction = VulnAuction(auctionAddr);
    }

    // ── 1. bid happy path ──

    function test_bid_happy_path() public {
        vm.prank(bidder1);
        auction.bid{value: 1 ether}();

        assertEq(auction.highestBidder(), bidder1);
        assertEq(auction.highestBid(), 1 ether);
    }

    // ── 2. bid below reserve reverts ──

    function test_bid_below_reserve_reverts() public {
        vm.prank(bidder1);
        vm.expectRevert("Below reserve");
        auction.bid{value: 0.5 ether}();
    }

    // ── 3. bid lower than current reverts ──

    function test_bid_lower_than_current_reverts() public {
        vm.prank(bidder1);
        auction.bid{value: 2 ether}();

        vm.prank(bidder2);
        vm.expectRevert("Bid too low");
        auction.bid{value: 1.5 ether}();
    }

    // ── 4. bid after end reverts ──

    function test_bid_after_end_reverts() public {
        vm.warp(block.timestamp + DURATION + 1);

        vm.prank(bidder1);
        vm.expectRevert("Auction ended");
        auction.bid{value: 1 ether}();
    }

    // ── 5. SC-only rejects non-SC ──

    function test_sc_only_rejects_non_sc() public {
        vm.prank(seller);
        address scAuctionAddr = factory.createAuction(operator, RESERVE, DURATION, true);
        VulnAuction scAuction = VulnAuction(scAuctionAddr);

        vm.prank(bidder1);
        vm.expectRevert("SC only");
        scAuction.bid{value: 1 ether}();
    }

    // ── 6. SC-only accepts SC ──

    function test_sc_only_accepts_sc() public {
        mockSC.setStatus(bidder1, true);

        vm.prank(seller);
        address scAuctionAddr = factory.createAuction(operator, RESERVE, DURATION, true);
        VulnAuction scAuction = VulnAuction(scAuctionAddr);

        vm.prank(bidder1);
        scAuction.bid{value: 1 ether}();

        assertEq(scAuction.highestBidder(), bidder1);
    }

    // ── 7. outbid: pending returns + withdraw ──

    function test_outbid_pending_returns() public {
        vm.prank(bidder1);
        auction.bid{value: 1 ether}();

        vm.prank(bidder2);
        auction.bid{value: 2 ether}();

        assertEq(auction.pendingReturns(bidder1), 1 ether);
        assertEq(auction.highestBidder(), bidder2);

        uint256 bidder1Before = bidder1.balance;
        vm.prank(bidder1);
        auction.withdraw();

        assertEq(bidder1.balance, bidder1Before + 1 ether);
        assertEq(auction.pendingReturns(bidder1), 0);
    }

    // ── 8. withdraw nothing reverts ──

    function test_withdraw_nothing_reverts() public {
        vm.prank(bidder1);
        vm.expectRevert("Nothing to withdraw");
        auction.withdraw();
    }

    // ── 9. end auction ──

    function test_end_auction() public {
        vm.prank(bidder1);
        auction.bid{value: 1 ether}();

        vm.warp(block.timestamp + DURATION);

        auction.endAuction();
        assertEq(uint256(auction.state()), uint256(VulnAuction.State.Ended));
    }

    // ── 10. end auction too early reverts ──

    function test_end_auction_too_early_reverts() public {
        vm.expectRevert("Not ended yet");
        auction.endAuction();
    }

    // ── 11. settle pays 90/10 ──

    function test_settle_pays_seller_platform() public {
        vm.prank(bidder1);
        auction.bid{value: 10 ether}();

        vm.warp(block.timestamp + DURATION);
        auction.endAuction();

        uint256 sellerBefore   = seller.balance;
        uint256 platformBefore = platform.balance;

        vm.prank(seller);
        auction.settle();

        // 10% fee = 1 ETH, seller gets 9 ETH
        assertEq(seller.balance, sellerBefore + 9 ether);
        assertEq(platform.balance, platformBefore + 1 ether);
        assertEq(uint256(auction.state()), uint256(VulnAuction.State.Settled));
    }

    // ── 12. settle non-seller reverts ──

    function test_settle_non_seller_reverts() public {
        vm.prank(bidder1);
        auction.bid{value: 1 ether}();

        vm.warp(block.timestamp + DURATION);
        auction.endAuction();

        vm.prank(stranger);
        vm.expectRevert("Only seller");
        auction.settle();
    }

    // ── 13. settle no bids reverts ──

    function test_settle_no_bids_reverts() public {
        vm.warp(block.timestamp + DURATION);
        auction.endAuction();

        vm.prank(seller);
        vm.expectRevert("No bids");
        auction.settle();
    }

    // ── 14. cancel no bids ──

    function test_cancel_no_bids() public {
        vm.prank(seller);
        auction.cancel();

        assertEq(uint256(auction.state()), uint256(VulnAuction.State.Cancelled));
    }

    // ── 15. cancel with bids reverts ──

    function test_cancel_with_bids_reverts() public {
        vm.prank(bidder1);
        auction.bid{value: 1 ether}();

        vm.prank(seller);
        vm.expectRevert("Has bids");
        auction.cancel();
    }

    // ── 16. cancel non-seller reverts ──

    function test_cancel_non_seller_reverts() public {
        vm.prank(stranger);
        vm.expectRevert("Only seller");
        auction.cancel();
    }

    // ── 17. factory tracks auctions ──

    function test_factory_tracks_auctions() public {
        assertEq(factory.auctionCount(), 1); // from setUp

        vm.prank(seller);
        factory.createAuction(operator, 2 ether, DURATION, true);

        assertEq(factory.auctionCount(), 2);
        address[] memory all = factory.getAuctions();
        assertEq(all.length, 2);
    }

    // ── 18. settle in wrong state reverts ──

    function test_settle_in_active_state_reverts() public {
        vm.prank(seller);
        vm.expectRevert("Wrong state");
        auction.settle();
    }

    // ── 19. bid in ended state reverts ──

    function test_bid_in_ended_state_reverts() public {
        vm.warp(block.timestamp + DURATION);
        auction.endAuction();

        vm.prank(bidder1);
        vm.expectRevert("Wrong state");
        auction.bid{value: 1 ether}();
    }

    // ── 20. multiple outbids accumulate pending returns ──

    function test_multiple_outbids_accumulate() public {
        vm.prank(bidder1);
        auction.bid{value: 1 ether}();

        vm.prank(bidder2);
        auction.bid{value: 2 ether}();

        vm.prank(bidder1);
        auction.bid{value: 3 ether}();

        // bidder2 was outbid once (2 ETH pending)
        assertEq(auction.pendingReturns(bidder2), 2 ether);
        // bidder1 was outbid once (1 ETH pending, now is highest with 3 ETH)
        assertEq(auction.pendingReturns(bidder1), 1 ether);
        assertEq(auction.highestBidder(), bidder1);
        assertEq(auction.highestBid(), 3 ether);
    }
}
