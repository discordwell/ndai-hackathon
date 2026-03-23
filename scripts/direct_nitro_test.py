"""Direct Nitro verification — bypasses HTTP, creates proposal in DB, runs verification."""
import asyncio
import json
import os
import uuid


async def main():
    from ndai.db.session import get_db_context
    from ndai.models.zk_identity import VulnIdentity
    from ndai.models.known_target import KnownTarget
    from ndai.models.verification_proposal import VerificationProposal
    from sqlalchemy import select

    pk = os.urandom(32).hex()

    async with get_db_context() as db:
        identity = VulnIdentity(public_key=pk, has_badge=True)
        db.add(identity)
        await db.commit()

        result = await db.execute(
            select(KnownTarget).where(KnownTarget.slug == "apache-httpd")
        )
        target = result.scalar_one()

        proposal = VerificationProposal(
            id=uuid.uuid4(),
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
        )
        db.add(proposal)
        await db.commit()
        pid = str(proposal.id)

    print("Proposal: %s" % pid, flush=True)

    from ndai.api.routers.proposals import _run_verification
    print("Running verification...", flush=True)
    await _run_verification(pid)

    async with get_db_context() as db:
        result = await db.execute(
            select(VerificationProposal).where(
                VerificationProposal.id == uuid.UUID(pid)
            )
        )
        p = result.scalar_one()
        print("=" * 60, flush=True)
        print("Status: %s" % p.status, flush=True)
        print("PCR0: %s" % p.attestation_pcr0, flush=True)
        print("Chain hash: %s" % p.verification_chain_hash, flush=True)
        if p.verification_result_json:
            print("Result: %s" % json.dumps(p.verification_result_json, indent=2), flush=True)
        if p.error_details:
            print("Error: %s" % p.error_details[:300], flush=True)


if __name__ == "__main__":
    asyncio.run(main())
