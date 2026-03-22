// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./VulnEscrow.sol";

/// @title VulnEscrowFactory — Deploys VulnEscrow contracts for zero-day deals
/// @notice The factory owner is the platform operator who receives the 10% fee.
contract VulnEscrowFactory {
    address[] public escrows;
    address public immutable platformAddress;

    event EscrowCreated(
        address indexed escrow,
        address indexed buyer,
        address indexed seller,
        uint256 price
    );

    constructor(address _platformAddress) {
        require(_platformAddress != address(0), "Invalid platform address");
        platformAddress = _platformAddress;
    }

    /// @notice Deploy a new VulnEscrow. Caller is the buyer, msg.value is the funding.
    function createEscrow(
        address seller,
        address operator,
        uint256 price,
        uint256 deadline,
        bool    isExclusive
    ) external payable returns (address) {
        VulnEscrow escrow = new VulnEscrow{value: msg.value}(
            msg.sender,
            seller,
            operator,
            platformAddress,
            price,
            deadline,
            isExclusive
        );
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller, price);
        return addr;
    }

    function getEscrows() external view returns (address[] memory) { return escrows; }
    function escrowCount() external view returns (uint256) { return escrows.length; }
}
