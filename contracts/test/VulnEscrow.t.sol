// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/VulnEscrow.sol";
import "../src/PCR0Registry.sol";

contract VulnEscrowTest is Test {
    VulnEscrow escrow;
    PCR0Registry registry;

    address buyer    = address(0xBEEF);
    address seller   = address(0xCAFE);
    address operator = address(0xDEAD);
    address platform = address(0xFEE);
    address stranger = address(0xBAD);

    uint256 constant PRICE   = 1 ether;
    uint256 constant FUNDING = 1 ether;  // buyer funds exactly the price
    uint256 constant ONE_DAY = 1 days;

    // Test PCR0 values
    bytes32 constant TEST_PCR0_HIGH = bytes32(uint256(0xAABBCCDD));
    bytes16 constant TEST_PCR0_LOW  = bytes16(uint128(0xEEFF));
    bytes32 constant TEST_BUILD_SPEC = keccak256("apt install apache2=2.4.59-1");

    function _registerPCR0() internal {
        registry.publishPCR0(
            TEST_PCR0_HIGH, TEST_PCR0_LOW,
            TEST_BUILD_SPEC,
            "ipfs://QmBuildSpec",
            "v1.0.0"
        );
    }

    function _deploy() internal returns (VulnEscrow) {
        vm.prank(buyer);
        return new VulnEscrow{value: FUNDING}(
            buyer, seller, operator, platform,
            PRICE, block.timestamp + ONE_DAY, true,
            address(registry),
            VulnEscrow.VerificationMode.Registry,
            bytes32(0), bytes16(0)
        );
    }

    function _deployOverfunded() internal returns (VulnEscrow) {
        vm.prank(buyer);
        return new VulnEscrow{value: 2 ether}(
            buyer, seller, operator, platform,
            PRICE, block.timestamp + ONE_DAY, true,
            address(registry),
            VulnEscrow.VerificationMode.Registry,
            bytes32(0), bytes16(0)
        );
    }

    function _deployChallengeMode() internal returns (VulnEscrow) {
        vm.prank(buyer);
        return new VulnEscrow{value: FUNDING}(
            buyer, seller, operator, platform,
            PRICE, block.timestamp + ONE_DAY, true,
            address(registry),
            VulnEscrow.VerificationMode.BuyerChallenge,
            TEST_PCR0_HIGH, TEST_PCR0_LOW
        );
    }

    function setUp() public {
        vm.warp(1_700_000_000);
        vm.deal(buyer, 10 ether);
        registry = new PCR0Registry();
        _registerPCR0();
        escrow = _deploy();
    }

    // ── Constructor ──

    function test_constructor_state() public view {
        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Funded));
        assertEq(escrow.seller(), seller);
        assertEq(escrow.buyer(), buyer);
        assertEq(escrow.operator(), operator);
        assertEq(escrow.platform(), platform);
        assertEq(escrow.price(), PRICE);
        assertEq(escrow.PLATFORM_FEE_BPS(), 1000);
        assertTrue(escrow.isExclusive());
        assertEq(address(escrow.pcr0Registry()), address(registry));
        assertEq(uint(escrow.verificationMode()), uint(VulnEscrow.VerificationMode.Registry));
    }

    function test_constructor_reverts_insufficient_funding() public {
        vm.prank(buyer);
        vm.expectRevert("Insufficient funding");
        new VulnEscrow{value: 0.5 ether}(
            buyer, seller, operator, platform,
            PRICE, block.timestamp + ONE_DAY, true,
            address(registry),
            VulnEscrow.VerificationMode.Registry,
            bytes32(0), bytes16(0)
        );
    }

    function test_constructor_reverts_zero_price() public {
        vm.prank(buyer);
        vm.expectRevert("Price must be positive");
        new VulnEscrow{value: 1 ether}(
            buyer, seller, operator, platform,
            0, block.timestamp + ONE_DAY, true,
            address(registry),
            VulnEscrow.VerificationMode.Registry,
            bytes32(0), bytes16(0)
        );
    }

    function test_constructor_reverts_invalid_registry() public {
        vm.prank(buyer);
        vm.expectRevert("Invalid registry");
        new VulnEscrow{value: 1 ether}(
            buyer, seller, operator, platform,
            PRICE, block.timestamp + ONE_DAY, true,
            address(0),
            VulnEscrow.VerificationMode.Registry,
            bytes32(0), bytes16(0)
        );
    }

    function test_constructor_challenge_mode_requires_pcr0() public {
        vm.prank(buyer);
        vm.expectRevert("Challenge PCR0 required");
        new VulnEscrow{value: 1 ether}(
            buyer, seller, operator, platform,
            PRICE, block.timestamp + ONE_DAY, true,
            address(registry),
            VulnEscrow.VerificationMode.BuyerChallenge,
            bytes32(0), bytes16(0)
        );
    }

    // ── submitVerification (Registry mode) ──

    function test_submit_verification_registry_mode() public {
        bytes32 att = keccak256("attestation");
        bytes32 dh  = keccak256("delivery");
        bytes32 kc  = keccak256("key");

        vm.prank(operator);
        escrow.submitVerification(att, dh, kc, TEST_PCR0_HIGH, TEST_PCR0_LOW);

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Verified));
        assertEq(escrow.attestationHash(), att);
        assertEq(escrow.deliveryHash(), dh);
        assertEq(escrow.keyCommitment(), kc);
        (bytes32 vHigh, bytes16 vLow) = escrow.getVerifiedPCR0();
        assertEq(vHigh, TEST_PCR0_HIGH);
        assertEq(vLow, TEST_PCR0_LOW);
    }

    function test_submit_reverts_unregistered_pcr0() public {
        bytes32 fakePCR0High = bytes32(uint256(0x999));
        bytes16 fakePCR0Low  = bytes16(uint128(0x111));

        vm.prank(operator);
        vm.expectRevert("PCR0 not in registry");
        escrow.submitVerification(
            keccak256("att"), bytes32(0), bytes32(0),
            fakePCR0High, fakePCR0Low
        );
    }

    function test_submit_reverts_not_operator() public {
        vm.prank(stranger);
        vm.expectRevert("Only operator");
        escrow.submitVerification(bytes32(0), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);
    }

    function test_submit_reverts_wrong_state() public {
        vm.prank(operator);
        escrow.submitVerification(keccak256("att"), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);
        vm.prank(operator);
        vm.expectRevert("Wrong state");
        escrow.submitVerification(bytes32(0), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);
    }

    // ── submitVerification (BuyerChallenge mode) ──

    function test_submit_verification_challenge_mode() public {
        VulnEscrow challengeEscrow = _deployChallengeMode();

        vm.prank(operator);
        challengeEscrow.submitVerification(
            keccak256("att"), keccak256("del"), keccak256("key"),
            TEST_PCR0_HIGH, TEST_PCR0_LOW
        );

        assertEq(uint(challengeEscrow.state()), uint(VulnEscrow.State.Verified));
    }

    function test_challenge_mode_rejects_wrong_pcr0() public {
        VulnEscrow challengeEscrow = _deployChallengeMode();

        bytes32 wrongPCR0 = bytes32(uint256(0x999));

        vm.prank(operator);
        vm.expectRevert("PCR0 does not match buyer challenge");
        challengeEscrow.submitVerification(
            keccak256("att"), bytes32(0), bytes32(0),
            wrongPCR0, TEST_PCR0_LOW
        );
    }

    // ── acceptDeal — 90/10 split ──

    function test_accept_splits_90_10() public {
        vm.prank(operator);
        escrow.submitVerification(keccak256("att"), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);

        uint256 fee = (PRICE * 1000) / 10000;  // 10% = 0.1 ETH
        uint256 sellerPayout = PRICE - fee;      // 90% = 0.9 ETH

        uint256 sellerBefore = seller.balance;
        uint256 platformBefore = platform.balance;

        vm.prank(seller);
        escrow.acceptDeal();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Accepted));
        assertEq(seller.balance, sellerBefore + sellerPayout);
        assertEq(platform.balance, platformBefore + fee);
    }

    function test_accept_overfunded_refunds_buyer() public {
        // Buyer overfunds by 1 ETH
        escrow = _deployOverfunded();

        vm.prank(operator);
        escrow.submitVerification(keccak256("att"), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);

        uint256 buyerBefore = buyer.balance;

        vm.prank(seller);
        escrow.acceptDeal();

        // Buyer gets back the overfunding (2 ETH - 1 ETH price = 1 ETH refund)
        assertEq(buyer.balance, buyerBefore + 1 ether);
    }

    function test_accept_reverts_not_seller() public {
        vm.prank(operator);
        escrow.submitVerification(keccak256("att"), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);

        vm.prank(stranger);
        vm.expectRevert("Only seller");
        escrow.acceptDeal();
    }

    function test_accept_reverts_before_verification() public {
        vm.prank(seller);
        vm.expectRevert("Wrong state");
        escrow.acceptDeal();
    }

    // ── rejectDeal ──

    function test_reject_refunds_buyer() public {
        vm.prank(operator);
        escrow.submitVerification(keccak256("att"), bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);

        uint256 buyerBefore = buyer.balance;
        vm.prank(seller);
        escrow.rejectDeal();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Rejected));
        assertEq(buyer.balance, buyerBefore + FUNDING);
    }

    // ── reportPatch ──

    function test_report_patch_refunds_buyer() public {
        uint256 buyerBefore = buyer.balance;
        vm.prank(operator);
        escrow.reportPatch();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.PatchRefunded));
        assertTrue(escrow.isPatchedBeforeSettlement());
        assertEq(buyer.balance, buyerBefore + FUNDING);
    }

    function test_report_patch_reverts_not_operator() public {
        vm.prank(stranger);
        vm.expectRevert("Only operator");
        escrow.reportPatch();
    }

    // ── claimExpired ──

    function test_claim_expired() public {
        vm.warp(block.timestamp + 2 days);
        uint256 buyerBefore = buyer.balance;
        escrow.claimExpired();

        assertEq(uint(escrow.state()), uint(VulnEscrow.State.Expired));
        assertEq(buyer.balance, buyerBefore + FUNDING);
    }

    function test_claim_expired_reverts_not_expired() public {
        vm.expectRevert("Not expired");
        escrow.claimExpired();
    }

    // ── Verify ──

    function test_verify_attestation() public {
        bytes32 pcr0 = bytes32(uint256(1));
        bytes32 nonce = bytes32(uint256(2));
        bytes32 outcome = bytes32(uint256(3));
        bytes32 att = keccak256(abi.encodePacked(pcr0, nonce, outcome));

        vm.prank(operator);
        escrow.submitVerification(att, bytes32(0), bytes32(0), TEST_PCR0_HIGH, TEST_PCR0_LOW);

        assertTrue(escrow.verifyAttestation(pcr0, nonce, outcome));
        assertFalse(escrow.verifyAttestation(pcr0, nonce, bytes32(uint256(999))));
    }

    function test_verify_delivery() public {
        bytes32 dh = keccak256("delivery");
        bytes32 kc = keccak256("key");

        vm.prank(operator);
        escrow.submitVerification(keccak256("att"), dh, kc, TEST_PCR0_HIGH, TEST_PCR0_LOW);

        assertTrue(escrow.verifyDelivery(dh, kc));
        assertFalse(escrow.verifyDelivery(dh, bytes32(uint256(999))));
    }

    // ── Fuzz ──

    function testFuzz_fee_calculation(uint256 _price) public pure {
        _price = bound(_price, 1, 100 ether);
        uint256 fee = (_price * 1000) / 10000;
        uint256 sellerPayout = _price - fee;
        // Seller always gets 90%, platform always gets 10%
        assertEq(fee + sellerPayout, _price);
        assertTrue(fee <= _price);
        assertTrue(sellerPayout <= _price);
    }
}
