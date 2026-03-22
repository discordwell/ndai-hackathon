// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/VulnEscrowFactory.sol";
import "../src/VerificationDeposit.sol";

contract Deploy is Script {
    address constant PLATFORM_ADDRESS = 0x2f063DC0Ce12Af40Aa252c2aE5f6b83Ad5f17aB9;
    address constant OPERATOR_ADDRESS = 0x2f063DC0Ce12Af40Aa252c2aE5f6b83Ad5f17aB9; // TEE operator

    function run() external {
        vm.startBroadcast();

        VulnEscrowFactory factory = new VulnEscrowFactory(PLATFORM_ADDRESS);
        console.log("Factory deployed at:", address(factory));

        VerificationDeposit vDeposit = new VerificationDeposit(OPERATOR_ADDRESS, PLATFORM_ADDRESS);
        console.log("VerificationDeposit deployed at:", address(vDeposit));

        vm.stopBroadcast();
        console.log("Platform fee address:", PLATFORM_ADDRESS);
        console.log("Operator address:", OPERATOR_ADDRESS);
    }
}
