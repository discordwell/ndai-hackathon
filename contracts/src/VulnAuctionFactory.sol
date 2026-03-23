// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "./VulnAuction.sol";

/// @title VulnAuctionFactory — Deploys per-exploit auction instances
contract VulnAuctionFactory {
    address[] public auctions;
    address public immutable platformAddress;
    address public immutable scContractAddress;

    event AuctionCreated(
        address indexed auction,
        address indexed seller,
        uint256 reservePrice,
        uint256 endTime,
        bool scOnly
    );

    constructor(address _platformAddress, address _scContractAddress) {
        require(_platformAddress  != address(0), "Invalid platform");
        require(_scContractAddress != address(0), "Invalid SC contract");
        platformAddress   = _platformAddress;
        scContractAddress = _scContractAddress;
    }

    /// @notice Create a new auction for an exploit.
    /// @param _operator TEE operator address
    /// @param _reservePrice Minimum bid in wei
    /// @param _duration Auction duration in seconds
    /// @param _scOnly Restrict bidding to Serious Customers
    function createAuction(
        address _operator,
        uint256 _reservePrice,
        uint256 _duration,
        bool    _scOnly
    ) external returns (address) {
        VulnAuction auction = new VulnAuction(
            msg.sender,        // seller
            _operator,
            platformAddress,
            scContractAddress,
            _reservePrice,
            _duration,
            _scOnly
        );

        address addr = address(auction);
        auctions.push(addr);

        emit AuctionCreated(addr, msg.sender, _reservePrice, block.timestamp + _duration, _scOnly);
        return addr;
    }

    function getAuctions() external view returns (address[] memory) {
        return auctions;
    }

    function auctionCount() external view returns (uint256) {
        return auctions.length;
    }
}
