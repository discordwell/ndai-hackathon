// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title BundleRegistry — on-chain JS bundle hash publication
/// @notice Allows the platform operator to publish the SHA-256 hash of the
///         frontend bundle so users can verify the code they're running
///         matches what was deployed. If the FBI compromises the server and
///         serves modified JS, users can detect it by comparing the on-chain
///         hash against a local SHA-256 of the served bundle.
contract BundleRegistry {
    address public immutable operator;
    bytes32 public currentBundleHash;
    uint256 public lastUpdated;

    event BundlePublished(bytes32 indexed hash, uint256 timestamp);

    constructor() {
        operator = msg.sender;
    }

    /// @notice Publish a new bundle hash. Only callable by operator.
    function publishHash(bytes32 hash) external {
        require(msg.sender == operator, "only operator");
        currentBundleHash = hash;
        lastUpdated = block.timestamp;
        emit BundlePublished(hash, block.timestamp);
    }
}
