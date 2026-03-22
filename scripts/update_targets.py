#!/usr/bin/env python3
"""CLI entry point for target auto-update.

Checks upstream release feeds for all active KnownTargets and updates
their versions when new releases are detected.

Usage:
    python -m scripts.update_targets

Can also be run via cron:
    0 */6 * * * cd /app && python -m scripts.update_targets
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndai.db.session import async_session, dispose_engine
from ndai.services.target_updater import TargetUpdater


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("update_targets")


async def main():
    """Run the target updater and print results."""
    logger.info("Starting target version check...")

    updater = TargetUpdater()

    async with async_session() as db:
        updates = await updater.check_all(db)

    if updates:
        logger.info("=" * 60)
        logger.info("Version updates applied:")
        for update in updates:
            logger.info(
                "  %s: %s -> %s",
                update["slug"],
                update["old_version"],
                update["new_version"],
            )
        logger.info("=" * 60)
    else:
        logger.info("No version updates needed. All targets are current.")

    await dispose_engine()
    return len(updates)


if __name__ == "__main__":
    count = asyncio.run(main())
    sys.exit(0 if count >= 0 else 1)
