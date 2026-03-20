// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./PokerTable.sol";

/// @title PokerTableFactory - Deploys per-table poker escrow contracts
contract PokerTableFactory {
    address[] public tables;

    event TableCreated(address indexed table, address indexed operator);

    function createTable(
        uint256 smallBlind,
        uint256 bigBlind,
        uint256 minBuyIn,
        uint256 maxBuyIn,
        uint8 maxSeats
    ) external returns (address) {
        PokerTable table = new PokerTable(
            msg.sender,
            smallBlind,
            bigBlind,
            minBuyIn,
            maxBuyIn,
            maxSeats
        );
        tables.push(address(table));
        emit TableCreated(address(table), msg.sender);
        return address(table);
    }

    function getTables() external view returns (address[] memory) {
        return tables;
    }

    function tableCount() external view returns (uint256) {
        return tables.length;
    }
}
