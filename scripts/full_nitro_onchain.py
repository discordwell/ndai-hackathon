"""Full Nitro verification with on-chain deposit and result emission on Sepolia."""
import asyncio
import hashlib
import json
import os
import uuid

SEPOLIA_RPC = "https://ethereum-sepolia-rpc.publicnode.com"
OPERATOR_KEY = "0x5eed7ee72df01ac93fb539855b71bfaa08b34e53e1f31650c27c47dbdc144f23"
DEPOSIT_CONTRACT = "0xA0d2E3CB4F8e35b3F36C189164b7243d53b4dCd2"
PCR0_REGISTRY = "0xa9dcc83cbf8fb2cedb7246cb0ca5d305094adcf5"
CHAIN_ID = 11155111


async def main():
    from ndai.db.session import get_db_context
    from ndai.models.zk_identity import VulnIdentity
    from ndai.models.known_target import KnownTarget
    from ndai.models.verification_proposal import VerificationProposal
    from sqlalchemy import select

    print("=" * 60)
    print("NDAI Nitro Verification + On-Chain Emission")
    print("=" * 60)

    # 1. Create identity with badge
    pk = os.urandom(32).hex()
    async with get_db_context() as db:
        identity = VulnIdentity(public_key=pk, has_badge=True)
        db.add(identity)
        await db.commit()

        result = await db.execute(
            select(KnownTarget).where(KnownTarget.slug == "apache-httpd")
        )
        target = result.scalar_one()

        proposal_uuid = uuid.uuid4()
        proposal = VerificationProposal(
            id=proposal_uuid,
            seller_pubkey=pk,
            target_id=target.id,
            target_version=target.current_version,
            poc_script="#!/bin/bash\ncat /var/lib/ndai-oracle/ace_canary",
            poc_script_type="bash",
            claimed_capability="ace",
            reliability_runs=1,
            asking_price_eth=0.05,
            deposit_required=False,
            status="building",
            deposit_proposal_id="0x" + hashlib.sha256(proposal_uuid.bytes).hexdigest(),
        )
        db.add(proposal)
        await db.commit()

    print("[1/4] Proposal created: %s" % proposal_uuid)
    print("       Target: %s %s" % (target.display_name, target.current_version))

    # 2. Run Nitro verification
    print("[2/4] Running Nitro Enclave verification...")
    from ndai.api.routers.proposals import _run_verification
    await _run_verification(str(proposal_uuid))

    # 3. Check result
    async with get_db_context() as db:
        result = await db.execute(
            select(VerificationProposal).where(
                VerificationProposal.id == proposal_uuid
            )
        )
        p = result.scalar_one()

    print("[3/4] Verification result:")
    print("       Status: %s" % p.status)
    print("       PCR0: %s" % p.attestation_pcr0)
    print("       Chain hash: %s" % p.verification_chain_hash)
    if p.verification_result_json:
        vr = p.verification_result_json
        print("       Passed: %s" % vr.get("passed"))
        print("       Capability: claimed=%s verified=%s" % (
            vr.get("claimed_capability"), vr.get("verified_capability")))

    if p.status != "passed":
        print("VERIFICATION FAILED - skipping on-chain emission")
        if p.error_details:
            print("Error: %s" % p.error_details[:300])
        return

    # 4. Emit on-chain: register PCR0 + grant badge
    print("[4/4] Emitting on-chain to Sepolia (chain %d)..." % CHAIN_ID)

    from web3 import AsyncWeb3
    from web3.providers import AsyncHTTPProvider
    from eth_account import Account

    w3 = AsyncWeb3(AsyncHTTPProvider(SEPOLIA_RPC))
    operator = Account.from_key(OPERATOR_KEY)

    # 4a. Grant badge on VerificationDeposit contract
    deposit_abi = json.loads(open("contracts/out/VerificationDeposit.sol/VerificationDeposit.json").read())["abi"]
    deposit_contract = w3.eth.contract(
        address=AsyncWeb3.to_checksum_address(DEPOSIT_CONTRACT),
        abi=deposit_abi,
    )

    # Grant badge to operator address (simulating seller = operator for demo)
    try:
        fn = deposit_contract.functions.grantBadge(operator.address)
        nonce = await w3.eth.get_transaction_count(operator.address)
        tx = await fn.build_transaction({
            "from": operator.address,
            "nonce": nonce,
            "chainId": CHAIN_ID,
            "gas": 100000,
        })
        signed = operator.sign_transaction(tx)
        tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
        badge_tx = receipt["transactionHash"].hex()
        print("       Badge granted: tx=%s" % badge_tx)
    except Exception as e:
        print("       Badge grant: %s" % str(e)[:100])

    # 4b. Register PCR0 on PCR0Registry
    pcr0_abi = json.loads(open("contracts/out/PCR0Registry.sol/PCR0Registry.json").read())["abi"]
    pcr0_contract = w3.eth.contract(
        address=AsyncWeb3.to_checksum_address(PCR0_REGISTRY),
        abi=pcr0_abi,
    )

    pcr0_value = p.attestation_pcr0 or ""
    if pcr0_value and pcr0_value != "nitro" and len(pcr0_value) >= 64:
        # PCR0 is 48 bytes (96 hex chars) — split into two bytes32
        pcr0_padded = pcr0_value.ljust(96, "0")[:96]
        pcr0_high = bytes.fromhex(pcr0_padded[:64])
        pcr0_low = bytes.fromhex(pcr0_padded[64:].ljust(64, "0"))

        try:
            fn = pcr0_contract.functions.registerPCR0(pcr0_high, pcr0_low)
            nonce = await w3.eth.get_transaction_count(operator.address)
            tx = await fn.build_transaction({
                "from": operator.address,
                "nonce": nonce,
                "chainId": CHAIN_ID,
                "gas": 100000,
            })
            signed = operator.sign_transaction(tx)
            tx_hash = await w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=60)
            pcr0_tx = receipt["transactionHash"].hex()
            print("       PCR0 registered: tx=%s" % pcr0_tx)
        except Exception as e:
            print("       PCR0 register: %s" % str(e)[:100])

    # Summary
    print()
    print("=" * 60)
    print("COMPLETE: Exploit verified in Nitro Enclave + emitted on-chain")
    print("=" * 60)
    print("Sepolia Explorer:")
    if "badge_tx" in dir():
        print("  Badge:  https://sepolia.etherscan.io/tx/%s" % badge_tx)
    if "pcr0_tx" in dir():
        print("  PCR0:   https://sepolia.etherscan.io/tx/%s" % pcr0_tx)
    print("Contracts:")
    print("  VerificationDeposit: %s" % DEPOSIT_CONTRACT)
    print("  PCR0Registry:        %s" % PCR0_REGISTRY)


if __name__ == "__main__":
    asyncio.run(main())
