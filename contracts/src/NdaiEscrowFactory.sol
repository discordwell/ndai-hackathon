// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./NdaiEscrow.sol";

contract NdaiEscrowFactory {
    address[] public escrows;

    event EscrowCreated(address indexed escrow, address indexed buyer, address indexed seller);

    function createEscrow(
        address seller, address operator, uint256 reservePrice, uint256 deadline
    ) external payable returns (address) {
        NdaiEscrow escrow = new NdaiEscrow{value: msg.value}(seller, operator, reservePrice, deadline);
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller);
        return addr;
    }

    function getEscrows() external view returns (address[] memory) { return escrows; }
    function escrowCount() external view returns (uint256) { return escrows.length; }
}
