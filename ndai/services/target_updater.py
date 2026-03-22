"""Target auto-updater — checks upstream release feeds and updates KnownTarget versions."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ndai.models.known_target import KnownTarget, TargetBuild
from ndai.services.feeds.chrome import ChromeReleaseChecker
from ndai.services.feeds.firefox import FirefoxReleaseChecker
from ndai.services.feeds.ubuntu import UbuntuReleaseChecker

logger = logging.getLogger(__name__)

# Map target slug prefixes to their feed checkers.
# A target with slug "chrome-linux" matches the "chrome" prefix.
_CHECKER_MAP: dict[str, type] = {
    "chrome": ChromeReleaseChecker,
    "chromium": ChromeReleaseChecker,
    "firefox": FirefoxReleaseChecker,
    "ubuntu": UbuntuReleaseChecker,
}


def _get_checker_for_slug(slug: str):
    """Return the appropriate release checker instance for a target slug.

    Matches the slug against known prefixes (e.g. "chrome-linux" -> ChromeReleaseChecker).
    Returns None if no checker is registered for this slug.
    """
    for prefix, checker_cls in _CHECKER_MAP.items():
        if slug.startswith(prefix):
            return checker_cls()
    return None


class TargetUpdater:
    """Checks upstream release feeds and updates KnownTarget versions."""

    async def check_all(self, db: AsyncSession) -> list[dict]:
        """Check all active targets for new versions.

        Iterates over all active KnownTargets, checks their upstream feed,
        and updates the current_version if a newer version is available.

        Args:
            db: Async database session.

        Returns:
            List of update dicts, each containing target slug, old version,
            and new version for targets that were updated.
        """
        stmt = select(KnownTarget).where(KnownTarget.is_active.is_(True))
        result = await db.execute(stmt)
        targets = result.scalars().all()

        updates: list[dict] = []
        for target in targets:
            try:
                update = await self.check_target(target, db)
                if update:
                    updates.append(update)
            except Exception:
                logger.exception("Failed to check target %s", target.slug)
                continue

        if updates:
            logger.info("Applied %d target version updates", len(updates))
        else:
            logger.info("All targets are up to date")

        return updates

    async def check_target(self, target: KnownTarget, db: AsyncSession) -> dict | None:
        """Check a single target for a new upstream version.

        Args:
            target: The KnownTarget to check.
            db: Async database session.

        Returns:
            Dict with update info (slug, old_version, new_version) if the
            version changed, or None if the target is already current.
        """
        checker = _get_checker_for_slug(target.slug)
        if checker is None:
            logger.debug("No feed checker for target %s, skipping", target.slug)
            return None

        latest_version = await checker.get_latest_version()
        if latest_version is None:
            logger.warning("Feed checker for %s returned None", target.slug)
            return None

        # Record the check timestamp regardless of whether the version changed
        target.last_version_check = datetime.now(timezone.utc)

        if latest_version == target.current_version:
            logger.debug("Target %s is current at %s", target.slug, target.current_version)
            await db.commit()
            return None

        old_version = target.current_version
        target.current_version = latest_version
        logger.info(
            "Target %s updated: %s -> %s",
            target.slug, old_version, latest_version,
        )

        await self._trigger_rebuild(target, latest_version, db)
        await db.commit()

        return {
            "slug": target.slug,
            "old_version": old_version,
            "new_version": latest_version,
        }

    async def _trigger_rebuild(self, target: KnownTarget, new_version: str, db: AsyncSession):
        """Trigger an EIF rebuild for a target with a new version.

        Creates a new TargetBuild record with status 'building'. The actual
        build is handled asynchronously by the build pipeline.

        Args:
            target: The KnownTarget being updated.
            new_version: The new version string.
            db: Async database session.
        """
        import hashlib

        cache_key = hashlib.sha256(
            f"{target.slug}:{new_version}".encode()
        ).hexdigest()

        build = TargetBuild(
            target_id=target.id,
            version=new_version,
            build_type="eif" if target.verification_method == "nitro" else "docker",
            cache_key=cache_key,
            artifact_path=f"/opt/ndai/eifs/{target.slug}-{new_version}-{cache_key[:12]}.eif",
            status="building",
        )
        db.add(build)

        # Mark any previous builds for this target as superseded
        stmt = (
            select(TargetBuild)
            .where(
                TargetBuild.target_id == target.id,
                TargetBuild.version != new_version,
                TargetBuild.status == "ready",
            )
        )
        result = await db.execute(stmt)
        old_builds = result.scalars().all()
        for old_build in old_builds:
            old_build.status = "superseded"

        logger.info(
            "Triggered rebuild for %s v%s (cache_key=%s, superseded %d old builds)",
            target.slug, new_version, cache_key[:12], len(old_builds),
        )
