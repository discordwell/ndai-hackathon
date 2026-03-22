// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./VulnEscrow.sol";

/// @title VulnEscrowFactory — Deploys VulnEscrow contracts for zero-day deals
/// @notice The factory owner is the platform operator who receives the 10% fee.
contract VulnEscrowFactory {
    address[] public escrows;
    address public immutable platformAddress; // Platform operator — receives 10% fee

    event EscrowCreated(
        address indexed escrow,
        address indexed buyer,
        address indexed seller,
        bool isExclusive
    );

    constructor(address _platformAddress) {
        require(_platformAddress != address(0), "Invalid platform address");
        platformAddress = _platformAddress;
    }

    /// @notice Deploy a new VulnEscrow for a vulnerability deal.
    ///         The platform fee address is automatically set from the factory.
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
            platformAddress,
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
