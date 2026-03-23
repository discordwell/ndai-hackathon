// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./VulnEscrow.sol";

/// @title VulnEscrowFactory — Deploys VulnEscrow contracts for zero-day deals
/// @notice The factory owner is the platform operator who receives the 10% fee.
contract VulnEscrowFactory {
    address[] public escrows;
    address public immutable platformAddress;
    address public immutable pcr0Registry;

    event EscrowCreated(
        address indexed escrow,
        address indexed buyer,
        address indexed seller,
        uint256 price
    );

    constructor(address _platformAddress, address _pcr0Registry) {
        require(_platformAddress != address(0), "Invalid platform address");
        require(_pcr0Registry != address(0), "Invalid registry address");
        platformAddress = _platformAddress;
        pcr0Registry = _pcr0Registry;
    }

    /// @notice Deploy a new VulnEscrow in Registry mode. Caller is the buyer.
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
            isExclusive,
            pcr0Registry,
            VulnEscrow.VerificationMode.Registry,
            bytes32(0),
            bytes16(0)
        );
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller, price);
        return addr;
    }

    /// @notice Deploy a new VulnEscrow in BuyerChallenge mode.
    ///         The buyer specifies the exact PCR0 they expect (from their own build).
    function createChallengeEscrow(
        address seller,
        address operator,
        uint256 price,
        uint256 deadline,
        bool    isExclusive,
        bytes32 challengePCR0High,
        bytes16 challengePCR0Low
    ) external payable returns (address) {
        VulnEscrow escrow = new VulnEscrow{value: msg.value}(
            msg.sender,
            seller,
            operator,
            platformAddress,
            price,
            deadline,
            isExclusive,
            pcr0Registry,
            VulnEscrow.VerificationMode.BuyerChallenge,
            challengePCR0High,
            challengePCR0Low
        );
        address addr = address(escrow);
        escrows.push(addr);
        emit EscrowCreated(addr, msg.sender, seller, price);
        return addr;
    }

    function getEscrows() external view returns (address[] memory) { return escrows; }
    function escrowCount() external view returns (uint256) { return escrows.length; }
}
