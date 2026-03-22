// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title PCR0Registry — on-chain enclave code attestation
/// @notice Publishes the PCR0 hash (SHA-384 of the Nitro Enclave Image) so
///         sellers can verify the exact code running in the verification enclave.
///         PCR0 is computed by `nitro-cli build-enclave` from the Dockerfile.
///         If the operator modifies the enclave code, PCR0 changes — sellers
///         can detect this by comparing on-chain vs their own local build.
contract PCR0Registry {
    address public immutable operator;

    /// @notice Current PCR0 hash (48 bytes = SHA-384, stored as two bytes32)
    bytes32 public pcr0High;  // first 32 bytes
    bytes16 public pcr0Low;   // last 16 bytes

    uint256 public lastUpdated;
    string public eifVersion;

    event PCR0Published(bytes32 pcr0High, bytes16 pcr0Low, string eifVersion, uint256 timestamp);

    constructor() {
        operator = msg.sender;
    }

    /// @notice Publish a new PCR0 hash. Only callable by operator.
    /// @param _pcr0High First 32 bytes of the SHA-384 PCR0
    /// @param _pcr0Low Last 16 bytes of the SHA-384 PCR0
    /// @param _eifVersion Human-readable version string (e.g., "v1.0.0-abc1234")
    function publishPCR0(bytes32 _pcr0High, bytes16 _pcr0Low, string calldata _eifVersion) external {
        require(msg.sender == operator, "only operator");
        pcr0High = _pcr0High;
        pcr0Low = _pcr0Low;
        eifVersion = _eifVersion;
        lastUpdated = block.timestamp;
        emit PCR0Published(_pcr0High, _pcr0Low, _eifVersion, block.timestamp);
    }

    /// @notice Get the full PCR0 as a hex string for easy comparison
    function getPCR0() external view returns (bytes32, bytes16) {
        return (pcr0High, pcr0Low);
    }
}
