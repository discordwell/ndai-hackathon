// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./VulnEscrow.sol";

/// @title VulnEscrowFactory — Deploys VulnEscrow contracts for zero-day deals
contract VulnEscrowFactory {
    address[] public escrows;

    event EscrowCreated(
        address indexed escrow,
        address indexed buyer,
        address indexed seller,
        bool isExclusive
    );

    /// @notice Deploy a new VulnEscrow for a vulnerability deal.
    /// @param seller             Vulnerability researcher address
    /// @param operator           TEE operator address
    /// @param reservePrice       Minimum acceptable price in wei
    /// @param deadline           Unix timestamp for deal expiry
    /// @param discoveryTimestamp  Unix timestamp when vulnerability was discovered
    /// @param embargoDays        Number of days for exclusivity embargo
    /// @param isExclusive        Whether this is an exclusive deal
    function createEscrow(
        address seller,
        address operator,
        uint256 reservePrice,
        uint256 deadline,
        uint256 discoveryTimestamp,
        uint256 embargoDays,
        bool    isExclusive
    ) external payable returns (address) {
        VulnEscrow escrow = new VulnEscrow{value: msg.value}(
            msg.sender,
            seller,
            operator,
            reservePrice,
            deadline,
            discoveryTimestamp,
            embargoDays,
            isExclusive
        );
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller, isExclusive);
        return addr;
    }

    function getEscrows() external view returns (address[] memory) { return escrows; }
    function escrowCount() external view returns (uint256) { return escrows.length; }
}
