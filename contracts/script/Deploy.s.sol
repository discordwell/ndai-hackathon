// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/NdaiEscrowFactory.sol";

contract Deploy is Script {
    function run() external {
        vm.startBroadcast();
        NdaiEscrowFactory factory = new NdaiEscrowFactory();
        vm.stopBroadcast();
        console.log("Factory deployed at:", address(factory));
    }
}
