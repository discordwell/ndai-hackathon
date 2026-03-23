"""Run verification inline (not as background task) to catch errors."""
import asyncio
import sys


async def main():
    proposal_id = sys.argv[1] if len(sys.argv) > 1 else None

    if not proposal_id:
        # Find latest building proposal
        from ndai.db.session import get_db_context
        from sqlalchemy import select
        from ndai.models.verification_proposal import VerificationProposal
        async with get_db_context() as db:
            result = await db.execute(
                select(VerificationProposal)
                .where(VerificationProposal.status.in_(["building", "queued"]))
                .order_by(VerificationProposal.created_at.desc())
                .limit(1)
            )
            p = result.scalar_one_or_none()
            if not p:
                print("No proposals to verify")
                return
            proposal_id = str(p.id)
            # Reset to building
            p.status = "building"
            await db.commit()

    print("Proposal: %s" % proposal_id, flush=True)

    from ndai.api.routers.proposals import _run_verification
    print("Running _run_verification...", flush=True)
    try:
        await _run_verification(proposal_id)
    except Exception as e:
        print("ERROR: %s" % e, flush=True)
        import traceback
        traceback.print_exc()

    # Check result
    from ndai.db.session import get_db_context
    from sqlalchemy import select
    from ndai.models.verification_proposal import VerificationProposal
    import uuid
    async with get_db_context() as db:
        result = await db.execute(
            select(VerificationProposal)
            .where(VerificationProposal.id == uuid.UUID(proposal_id))
        )
        p = result.scalar_one_or_none()
        if p:
            print("Status: %s" % p.status, flush=True)
            print("PCR0: %s" % p.attestation_pcr0, flush=True)
            print("Chain hash: %s" % p.verification_chain_hash, flush=True)
            print("Result: %s" % p.verification_result_json, flush=True)
            print("Error: %s" % p.error_details, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
