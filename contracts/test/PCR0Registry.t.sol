// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/PCR0Registry.sol";

contract PCR0RegistryTest is Test {
    PCR0Registry registry;

    bytes32 constant PCR0_HIGH = bytes32(uint256(0xAABBCCDD));
    bytes16 constant PCR0_LOW  = bytes16(uint128(0xEEFF));
    bytes32 constant BUILD_SPEC = keccak256("apt install apache2=2.4.59-1");
    string  constant BUILD_URI  = "ipfs://QmBuildSpec123";
    string  constant VERSION    = "v1.0.0-abc1234";

    function setUp() public {
        registry = new PCR0Registry();
    }

    // ── publishPCR0 ──

    function test_publish_stores_record() public {
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, VERSION);

        (bytes32 high, bytes16 low) = registry.getPCR0();
        assertEq(high, PCR0_HIGH);
        assertEq(low, PCR0_LOW);

        (bytes32 specHash, string memory uri) = registry.getBuildSpec();
        assertEq(specHash, BUILD_SPEC);
        assertEq(uri, BUILD_URI);
    }

    function test_publish_emits_event() public {
        vm.expectEmit(true, false, false, true);
        emit PCR0Registry.PCR0Published(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, VERSION, block.timestamp, 0);
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, VERSION);
    }

    function test_publish_reverts_not_operator() public {
        vm.prank(address(0xBAD));
        vm.expectRevert("only operator");
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, VERSION);
    }

    function test_publish_reverts_no_build_spec() public {
        vm.expectRevert("build spec hash required");
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, bytes32(0), BUILD_URI, VERSION);
    }

    // ── verifyPCR0 ──

    function test_verify_registered_pcr0() public {
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, VERSION);

        (bool registered, bytes32 specHash, string memory uri) = registry.verifyPCR0(PCR0_HIGH, PCR0_LOW);
        assertTrue(registered);
        assertEq(specHash, BUILD_SPEC);
        assertEq(uri, BUILD_URI);
    }

    function test_verify_unregistered_pcr0() public view {
        bytes32 fakeHigh = bytes32(uint256(0x999));
        bytes16 fakeLow  = bytes16(uint128(0x111));

        (bool registered,,) = registry.verifyPCR0(fakeHigh, fakeLow);
        assertFalse(registered);
    }

    // ── History ──

    function test_history_tracks_all_publications() public {
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, "v1.0.0");

        bytes32 pcr0High2 = bytes32(uint256(0x11223344));
        bytes16 pcr0Low2  = bytes16(uint128(0x5566));
        bytes32 buildSpec2 = keccak256("apt install nginx=1.24.0-1");

        registry.publishPCR0(pcr0High2, pcr0Low2, buildSpec2, "ipfs://QmNginx", "v2.0.0");

        assertEq(registry.historyLength(), 2);

        // First record still verifiable
        (bool reg1, bytes32 spec1,) = registry.verifyPCR0(PCR0_HIGH, PCR0_LOW);
        assertTrue(reg1);
        assertEq(spec1, BUILD_SPEC);

        // Second record also verifiable
        (bool reg2, bytes32 spec2,) = registry.verifyPCR0(pcr0High2, pcr0Low2);
        assertTrue(reg2);
        assertEq(spec2, buildSpec2);

        // Current is the latest
        (bytes32 curHigh, bytes16 curLow) = registry.getPCR0();
        assertEq(curHigh, pcr0High2);
        assertEq(curLow, pcr0Low2);
    }

    function test_overwrite_pcr0_updates_history_index() public {
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, BUILD_SPEC, BUILD_URI, "v1.0.0");
        bytes32 newBuildSpec = keccak256("updated build");
        registry.publishPCR0(PCR0_HIGH, PCR0_LOW, newBuildSpec, "ipfs://QmUpdated", "v1.0.1");

        assertEq(registry.historyLength(), 2);

        // verifyPCR0 returns the latest index for this PCR0
        (bool reg, bytes32 specHash,) = registry.verifyPCR0(PCR0_HIGH, PCR0_LOW);
        assertTrue(reg);
        assertEq(specHash, newBuildSpec);
    }
}
