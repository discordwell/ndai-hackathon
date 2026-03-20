// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/NdaiEscrowFactory.sol";
import "../src/NdaiEscrow.sol";

contract NdaiEscrowFactoryTest is Test {
    NdaiEscrowFactory factory;

    address buyer    = address(0xBEEF);
    address seller   = address(0xCAFE);
    address operator = address(0xDEAD);

    uint256 constant BUDGET  = 1 ether;
    uint256 constant RESERVE = 0.1 ether;
    uint256 constant ONE_DAY = 1 days;

    function setUp() public {
        vm.deal(buyer, 10 ether);
        factory = new NdaiEscrowFactory();
    }

    // ------------------------------------------------------------------ //
    //  createEscrow — basic deployment and funding                        //
    // ------------------------------------------------------------------ //

    function test_CreateEscrow_DeploysAndFunds() public {
        vm.prank(buyer);
        address escrowAddr = factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );

        // Address must be non-zero
        assertTrue(escrowAddr != address(0), "Escrow address is zero");

        // Balance must equal the funded amount
        assertEq(escrowAddr.balance, BUDGET, "Escrow balance incorrect");

        // Verify escrow fields
        NdaiEscrow escrow = NdaiEscrow(payable(escrowAddr));
        assertEq(escrow.buyer(),        buyer, "Wrong buyer");
        assertEq(escrow.seller(),       seller,           "Wrong seller");
        assertEq(escrow.operator(),     operator,         "Wrong operator");
        assertEq(uint(escrow.state()),  uint(NdaiEscrow.State.Funded), "Wrong state");
    }

    // ------------------------------------------------------------------ //
    //  Registry — getEscrows() returns all created escrows                //
    // ------------------------------------------------------------------ //

    function test_Registry_TracksMultipleEscrows() public {
        vm.deal(buyer, 20 ether);

        vm.prank(buyer);
        address addr1 = factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );

        vm.prank(buyer);
        address addr2 = factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );

        address[] memory all = factory.getEscrows();
        assertEq(all.length, 2, "Registry should have 2 escrows");
        assertEq(all[0], addr1, "First escrow address mismatch");
        assertEq(all[1], addr2, "Second escrow address mismatch");
    }

    // ------------------------------------------------------------------ //
    //  escrowCount() increments on each createEscrow call                 //
    // ------------------------------------------------------------------ //

    function test_EscrowCount_Increments() public {
        assertEq(factory.escrowCount(), 0, "Initial count should be 0");

        vm.deal(buyer, 30 ether);

        vm.prank(buyer);
        factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );
        assertEq(factory.escrowCount(), 1, "Count should be 1 after first create");

        vm.prank(buyer);
        factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );
        assertEq(factory.escrowCount(), 2, "Count should be 2 after second create");

        vm.prank(buyer);
        factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );
        assertEq(factory.escrowCount(), 3, "Count should be 3 after third create");
    }

    // ------------------------------------------------------------------ //
    //  EscrowCreated event — emitted with correct args                    //
    // ------------------------------------------------------------------ //

    function test_CreateEscrow_EmitsEscrowCreatedEvent() public {
        // We need to predict the escrow address. Compute it first by simulating
        // the call, then verify the event in a second call with a fresh buyer.
        address buyer2 = address(0xFEED);
        vm.deal(buyer2, 10 ether);

        // Capture the event by checking topics: buyer2 as buyer, seller as seller
        vm.prank(buyer2);
        vm.expectEmit(false, true, true, false); // addr unknown, buyer2 indexed, seller indexed
        emit NdaiEscrowFactory.EscrowCreated(address(0), buyer2, seller);
        factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );
    }

    // ------------------------------------------------------------------ //
    //  createEscrow returns correct address (matches registry)            //
    // ------------------------------------------------------------------ //

    function test_CreateEscrow_ReturnedAddressMatchesRegistry() public {
        vm.prank(buyer);
        address returned = factory.createEscrow{value: BUDGET}(
            seller, operator, RESERVE, block.timestamp + ONE_DAY
        );

        address[] memory all = factory.getEscrows();
        assertEq(all.length, 1, "Registry length should be 1");
        assertEq(all[0], returned, "Returned address must match registry entry");
    }
}
