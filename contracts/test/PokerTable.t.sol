// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/PokerTable.sol";
import "../src/PokerTableFactory.sol";

contract PokerTableTest is Test {
    PokerTable table;
    address operator = address(1);
    address player1 = address(2);
    address player2 = address(3);
    address player3 = address(4);

    uint256 constant SB = 0.001 ether;
    uint256 constant BB = 0.002 ether;
    uint256 constant MIN_BUY = 0.02 ether;
    uint256 constant MAX_BUY = 2 ether;

    function setUp() public {
        table = new PokerTable(operator, SB, BB, MIN_BUY, MAX_BUY, 6);
        vm.deal(player1, 10 ether);
        vm.deal(player2, 10 ether);
        vm.deal(player3, 10 ether);
    }

    // --- Deposit ---

    function test_deposit() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        assertEq(table.getBalance(player1), 1 ether);
        assertEq(table.getPlayerCount(), 1);
        assertTrue(table.isSeated(player1));
    }

    function test_deposit_below_minimum_reverts() public {
        vm.prank(player1);
        vm.expectRevert("Below min buy-in");
        table.deposit{value: 0.01 ether}();
    }

    function test_deposit_above_maximum_reverts() public {
        vm.prank(player1);
        vm.expectRevert("Exceeds max buy-in");
        table.deposit{value: 3 ether}();
    }

    function test_deposit_multiple_players() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(player2);
        table.deposit{value: 0.5 ether}();
        assertEq(table.getPlayerCount(), 2);
    }

    function test_rebuy_existing_player() public {
        vm.prank(player1);
        table.deposit{value: 0.5 ether}();
        vm.prank(player1);
        table.deposit{value: 0.3 ether}();
        assertEq(table.getBalance(player1), 0.8 ether);
        assertEq(table.getPlayerCount(), 1); // still just one player
    }

    // --- Withdraw ---

    function test_withdraw() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();

        uint256 balBefore = player1.balance;
        vm.prank(player1);
        table.withdraw();
        assertEq(player1.balance, balBefore + 1 ether);
        assertEq(table.getBalance(player1), 0);
        assertFalse(table.isSeated(player1));
    }

    function test_withdraw_no_balance_reverts() public {
        vm.prank(player1);
        vm.expectRevert("No balance");
        table.withdraw();
    }

    // --- Settlement ---

    function test_settle_hand() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(player2);
        table.deposit{value: 1 ether}();

        // Player1 wins 0.1 ETH from player2
        address[] memory winners = new address[](1);
        winners[0] = player1;
        uint256[] memory winAmounts = new uint256[](1);
        winAmounts[0] = 0.1 ether;
        address[] memory losers = new address[](1);
        losers[0] = player2;
        uint256[] memory lossAmounts = new uint256[](1);
        lossAmounts[0] = 0.1 ether;

        bytes32 resultHash = keccak256("hand1");

        vm.prank(operator);
        table.settleHand(1, resultHash, winners, winAmounts, losers, lossAmounts);

        assertEq(table.getBalance(player1), 1.1 ether);
        assertEq(table.getBalance(player2), 0.9 ether);
        assertEq(table.lastSettledHand(), 1);
        assertTrue(table.verifyHandResult(1, resultHash));
    }

    function test_settle_not_zero_sum_reverts() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(player2);
        table.deposit{value: 1 ether}();

        address[] memory winners = new address[](1);
        winners[0] = player1;
        uint256[] memory winAmounts = new uint256[](1);
        winAmounts[0] = 0.2 ether;
        address[] memory losers = new address[](1);
        losers[0] = player2;
        uint256[] memory lossAmounts = new uint256[](1);
        lossAmounts[0] = 0.1 ether;

        vm.prank(operator);
        vm.expectRevert("Not zero-sum");
        table.settleHand(1, bytes32(0), winners, winAmounts, losers, lossAmounts);
    }

    function test_settle_wrong_hand_number_reverts() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(player2);
        table.deposit{value: 1 ether}();

        address[] memory empty = new address[](0);
        uint256[] memory emptyAmounts = new uint256[](0);

        vm.prank(operator);
        vm.expectRevert("Wrong hand number");
        table.settleHand(5, bytes32(0), empty, emptyAmounts, empty, emptyAmounts);
    }

    function test_settle_non_operator_reverts() public {
        address[] memory empty = new address[](0);
        uint256[] memory emptyAmounts = new uint256[](0);

        vm.prank(player1);
        vm.expectRevert("Only operator");
        table.settleHand(1, bytes32(0), empty, emptyAmounts, empty, emptyAmounts);
    }

    function test_settle_sequential_hands() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(player2);
        table.deposit{value: 1 ether}();

        address[] memory winners = new address[](1);
        winners[0] = player1;
        uint256[] memory winAmounts = new uint256[](1);
        winAmounts[0] = 0.05 ether;
        address[] memory losers = new address[](1);
        losers[0] = player2;
        uint256[] memory lossAmounts = new uint256[](1);
        lossAmounts[0] = 0.05 ether;

        vm.prank(operator);
        table.settleHand(1, keccak256("h1"), winners, winAmounts, losers, lossAmounts);
        vm.prank(operator);
        table.settleHand(2, keccak256("h2"), winners, winAmounts, losers, lossAmounts);

        assertEq(table.lastSettledHand(), 2);
        assertEq(table.getBalance(player1), 1.1 ether);
        assertEq(table.getBalance(player2), 0.9 ether);
    }

    // --- Close table ---

    function test_close_table() public {
        vm.prank(operator);
        table.closeTable();
        assertFalse(table.isOpen());
    }

    function test_deposit_after_close_reverts() public {
        vm.prank(operator);
        table.closeTable();
        vm.prank(player1);
        vm.expectRevert("Table closed");
        table.deposit{value: 1 ether}();
    }

    function test_emergency_withdraw() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(operator);
        table.closeTable();

        uint256 balBefore = player1.balance;
        vm.prank(player1);
        table.emergencyWithdraw();
        assertEq(player1.balance, balBefore + 1 ether);
    }

    function test_emergency_withdraw_while_open_reverts() public {
        vm.prank(player1);
        table.deposit{value: 1 ether}();
        vm.prank(player1);
        vm.expectRevert("Table still open");
        table.emergencyWithdraw();
    }

    // --- Factory ---

    function test_factory_creates_table() public {
        PokerTableFactory factory = new PokerTableFactory();
        address tableAddr = factory.createTable(SB, BB, MIN_BUY, MAX_BUY, 9);
        assertTrue(tableAddr != address(0));
        assertEq(factory.tableCount(), 1);
        assertEq(factory.getTables()[0], tableAddr);
    }
}
