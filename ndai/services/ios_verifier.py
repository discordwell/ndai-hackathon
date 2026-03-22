"""iOS verification backend — stub for Corellium integration.

Currently a manual review stub. When a seller submits a proposal against an
iOS target, it's queued for manual operator review. The operator provisions
a Corellium virtual device and runs verification manually.

Future: full Corellium REST API integration when demand justifies the
~$500/month cost per device slot.
"""

import logging
from typing import Any

from ndai.models.known_target import KnownTarget
from ndai.models.verification_proposal import VerificationProposal
from ndai.services.verification_dispatcher import VerificationOutcome

logger = logging.getLogger(__name__)


class IOSVerifier:
    """iOS verification backend — currently manual review only."""

    async def verify(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """Queue an iOS proposal for manual review.

        Steps:
        1. Validate the proposal format
        2. Log for admin notification
        3. Return manual_review status

        Future Corellium integration would:
        1. Create virtual device via POST /api/v1/instances
        2. Set iOS version via the device config
        3. Upload exploit via the Corellium agent API
        4. Monitor for canary retrieval
        5. Capture results via /api/v1/instances/{id}/agent/run
        6. Tear down device
        """
        logger.info(
            "iOS verification proposal %s queued for manual review "
            "(target: %s %s, capability: %s, escrow: $%d)",
            proposal.id,
            target.display_name,
            target.current_version,
            proposal.claimed_capability,
            target.escrow_amount_usd,
        )

        if progress_callback:
            await progress_callback("manual_review", {
                "message": (
                    "iOS verification requires manual review. "
                    "A platform operator will provision a Corellium device "
                    "and verify your exploit. This typically takes 24-72 hours."
                ),
                "escrow_amount_usd": target.escrow_amount_usd,
            })

        return VerificationOutcome(
            success=False,
            status="manual_review",
            error=(
                "iOS verification is currently manual. "
                "Your proposal has been queued for operator review."
            ),
        )
