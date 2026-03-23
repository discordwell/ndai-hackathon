// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./NdaiEscrow.sol";

/// @title NdaiEscrowFactory — Deploys per-deal NdaiEscrow instances
/// @author NDAI (arxiv:2502.07924)
/// @notice Factory for creating escrow contracts for each NDAI negotiation.
///   The caller (buyer) funds the escrow at creation time.
contract NdaiEscrowFactory {
    address[] public escrows;

    event EscrowCreated(address indexed escrow, address indexed buyer, address indexed seller);

    /// @notice Create a new escrow for a deal. Caller is the buyer and must send ETH.
    /// @param seller Address of the seller (inventor)
    /// @param operator Address of the TEE operator
    /// @param reservePrice Minimum acceptable price (in wei)
    /// @param deadline Unix timestamp for deal expiration
    /// @return The address of the newly deployed NdaiEscrow contract
    function createEscrow(
        address seller, address operator, uint256 reservePrice, uint256 deadline
    ) external payable returns (address) {
        NdaiEscrow escrow = new NdaiEscrow{value: msg.value}(msg.sender, seller, operator, reservePrice, deadline);
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller);
        return addr;
    }

    /// @notice Get all deployed escrow addresses
    /// @return Array of escrow contract addresses
    function getEscrows() external view returns (address[] memory) { return escrows; }

    /// @notice Get the total number of escrows created
    /// @return Count of escrow contracts
    function escrowCount() external view returns (uint256) { return escrows.length; }
}
