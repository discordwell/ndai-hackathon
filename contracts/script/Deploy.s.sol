// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Script.sol";
import "../src/PCR0Registry.sol";
import "../src/VulnEscrowFactory.sol";
import "../src/NdaiEscrowFactory.sol";
import "../src/VerificationDeposit.sol";
import "../src/SeriousCustomer.sol";
import "../src/VulnAuctionFactory.sol";

contract Deploy is Script {
    address constant PLATFORM_ADDRESS = 0x2f063DC0Ce12Af40Aa252c2aE5f6b83Ad5f17aB9;
    address constant OPERATOR_ADDRESS = 0x2f063DC0Ce12Af40Aa252c2aE5f6b83Ad5f17aB9; // TEE operator
    // Chainlink ETH/USD on Base Sepolia
    address constant CHAINLINK_ETH_USD = 0x4Adc67D868EC7e981A90f1a33f09F78c2eAf637A;

    function run() external {
        vm.startBroadcast();

        PCR0Registry registry = new PCR0Registry();
        console.log("PCR0Registry deployed at:", address(registry));

        VulnEscrowFactory factory = new VulnEscrowFactory(PLATFORM_ADDRESS, address(registry));
        console.log("VulnEscrowFactory deployed at:", address(factory));

        NdaiEscrowFactory ndaiFactory = new NdaiEscrowFactory();
        console.log("NdaiEscrowFactory deployed at:", address(ndaiFactory));

        VerificationDeposit vDeposit = new VerificationDeposit(OPERATOR_ADDRESS, PLATFORM_ADDRESS);
        console.log("VerificationDeposit deployed at:", address(vDeposit));

        SeriousCustomer sc = new SeriousCustomer(OPERATOR_ADDRESS, PLATFORM_ADDRESS, CHAINLINK_ETH_USD);
        console.log("SeriousCustomer deployed at:", address(sc));

        VulnAuctionFactory aFactory = new VulnAuctionFactory(PLATFORM_ADDRESS, address(sc));
        console.log("VulnAuctionFactory deployed at:", address(aFactory));

        vm.stopBroadcast();
        console.log("Platform fee address:", PLATFORM_ADDRESS);
        console.log("Operator address:", OPERATOR_ADDRESS);
    }
}
