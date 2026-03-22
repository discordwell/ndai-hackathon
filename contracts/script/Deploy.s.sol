// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/VulnEscrowFactory.sol";

contract Deploy is Script {
    address constant PLATFORM_ADDRESS = 0x2f063DC0Ce12Af40Aa252c2aE5f6b83Ad5f17aB9;

    function run() external {
        vm.startBroadcast();
        VulnEscrowFactory factory = new VulnEscrowFactory(PLATFORM_ADDRESS);
        vm.stopBroadcast();
        console.log("Factory deployed at:", address(factory));
        console.log("Platform fee address:", PLATFORM_ADDRESS);
    }
}
