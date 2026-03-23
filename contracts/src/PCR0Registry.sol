// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title PCR0Registry — on-chain enclave code attestation with build spec tracking
/// @notice Publishes PCR0 hashes alongside their build specifications so anyone
///         can independently verify the enclave image. The build spec (Dockerfile +
///         target software versions) is the source of truth — same spec, same PCR0.
///
///         Anti-self-proof: the operator publishes a build spec hash with every PCR0.
///         Anyone can run the same build command and verify the PCR0 matches.
///         If the operator uses a rigged target, the build spec will reveal it.
contract PCR0Registry {
    address public immutable operator;

    struct ImageRecord {
        bytes32 pcr0High;       // first 32 bytes of SHA-384 PCR0
        bytes16 pcr0Low;        // last 16 bytes of SHA-384 PCR0
        bytes32 buildSpecHash;  // SHA-256 of the full build spec (Dockerfile + args)
        string  buildSpecURI;   // IPFS/HTTP URI to the full build spec
        string  eifVersion;     // human-readable version string
        uint256 timestamp;
    }

    /// @notice Current (latest) image record
    ImageRecord public current;

    /// @notice Historical record of all published images, indexed sequentially
    ImageRecord[] public history;

    /// @notice Lookup: given a PCR0, is it registered and what build spec produced it?
    ///         Key: keccak256(abi.encodePacked(pcr0High, pcr0Low))
    mapping(bytes32 => uint256) public pcr0ToHistoryIndex;
    mapping(bytes32 => bool)    public pcr0Registered;

    event PCR0Published(
        bytes32 pcr0High,
        bytes16 pcr0Low,
        bytes32 buildSpecHash,
        string  buildSpecURI,
        string  eifVersion,
        uint256 timestamp,
        uint256 indexed historyIndex
    );

    constructor() {
        operator = msg.sender;
    }

    /// @notice Publish a new PCR0 with its build spec. Only callable by operator.
    /// @param _pcr0High First 32 bytes of the SHA-384 PCR0
    /// @param _pcr0Low Last 16 bytes of the SHA-384 PCR0
    /// @param _buildSpecHash SHA-256 hash of the build specification
    /// @param _buildSpecURI URI to the full build spec (IPFS preferred)
    /// @param _eifVersion Human-readable version string (e.g., "v1.0.0-abc1234")
    function publishPCR0(
        bytes32 _pcr0High,
        bytes16 _pcr0Low,
        bytes32 _buildSpecHash,
        string calldata _buildSpecURI,
        string calldata _eifVersion
    ) external {
        require(msg.sender == operator, "only operator");
        require(_buildSpecHash != bytes32(0), "build spec hash required");

        bytes32 pcr0Key = keccak256(abi.encodePacked(_pcr0High, _pcr0Low));
        uint256 idx = history.length;

        ImageRecord memory record = ImageRecord({
            pcr0High: _pcr0High,
            pcr0Low: _pcr0Low,
            buildSpecHash: _buildSpecHash,
            buildSpecURI: _buildSpecURI,
            eifVersion: _eifVersion,
            timestamp: block.timestamp
        });

        current = record;
        history.push(record);
        pcr0ToHistoryIndex[pcr0Key] = idx;
        pcr0Registered[pcr0Key] = true;

        emit PCR0Published(
            _pcr0High, _pcr0Low, _buildSpecHash,
            _buildSpecURI, _eifVersion, block.timestamp, idx
        );
    }

    /// @notice Check if a PCR0 is registered and get its build spec hash.
    ///         Buyers call this to verify the verification enclave before committing funds.
    function verifyPCR0(bytes32 _pcr0High, bytes16 _pcr0Low)
        external view returns (bool registered, bytes32 buildSpecHash, string memory buildSpecURI)
    {
        bytes32 pcr0Key = keccak256(abi.encodePacked(_pcr0High, _pcr0Low));
        if (!pcr0Registered[pcr0Key]) {
            return (false, bytes32(0), "");
        }
        ImageRecord storage record = history[pcr0ToHistoryIndex[pcr0Key]];
        return (true, record.buildSpecHash, record.buildSpecURI);
    }

    /// @notice Get the full PCR0 as raw bytes for comparison
    function getPCR0() external view returns (bytes32, bytes16) {
        return (current.pcr0High, current.pcr0Low);
    }

    /// @notice Get the build spec for the current image
    function getBuildSpec() external view returns (bytes32 buildSpecHash, string memory buildSpecURI) {
        return (current.buildSpecHash, current.buildSpecURI);
    }

    /// @notice Total number of published images
    function historyLength() external view returns (uint256) {
        return history.length;
    }
}
