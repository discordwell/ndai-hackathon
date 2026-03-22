// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../src/BundleRegistry.sol";

contract BundleRegistryTest is Test {
    BundleRegistry registry;

    address deployer = address(this);
    address stranger = address(0xBAD);

    function setUp() public {
        registry = new BundleRegistry();
    }

    // ── Constructor ──

    function testOperatorIsDeployer() public view {
        assertEq(registry.operator(), deployer);
    }

    // ── publishHash ──

    function testPublishHash() public {
        bytes32 hash = keccak256("bundle-v1");

        vm.expectEmit(true, false, false, true);
        emit BundleRegistry.BundlePublished(hash, block.timestamp);

        registry.publishHash(hash);

        assertEq(registry.currentBundleHash(), hash);
        assertEq(registry.lastUpdated(), block.timestamp);
    }

    function testPublishHashUpdatesState() public {
        bytes32 hashA = keccak256("bundle-v1");
        bytes32 hashB = keccak256("bundle-v2");

        registry.publishHash(hashA);
        assertEq(registry.currentBundleHash(), hashA);

        vm.warp(block.timestamp + 1 hours);

        registry.publishHash(hashB);
        assertEq(registry.currentBundleHash(), hashB);
        assertEq(registry.lastUpdated(), block.timestamp);
    }

    function testNonOperatorCannotPublish() public {
        vm.prank(stranger);
        vm.expectRevert("only operator");
        registry.publishHash(keccak256("evil"));
    }

    function testInitialHashIsZero() public view {
        assertEq(registry.currentBundleHash(), bytes32(0));
    }
}
