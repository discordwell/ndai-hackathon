"""Chrome release feed checker — fetches latest stable version from Chromium Dashboard."""

import logging

import httpx

logger = logging.getLogger(__name__)


class ChromeReleaseChecker:
    """Checks latest Chrome stable version from Chromium Dashboard API."""

    FEED_URL = "https://chromiumdash.appspot.com/fetch/milestones"

    async def get_latest_version(self) -> str | None:
        """Fetch latest stable Chrome version.

        Queries the Chromium Dashboard milestones API and returns the version
        string for the most recent stable milestone.

        Returns:
            Version string (e.g. "124.0.6367.91") or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self.FEED_URL)
                resp.raise_for_status()

            milestones = resp.json()
            if not isinstance(milestones, list) or len(milestones) == 0:
                logger.warning("Chrome feed returned empty or non-list response")
                return None

            # Milestones are returned sorted by milestone number descending.
            # Find the first one that has a stable chromium_main_branch_position
            # (i.e. has actually shipped to stable).
            for milestone in milestones:
                version = milestone.get("version")
                if version:
                    logger.info("Latest Chrome stable version: %s", version)
                    return str(version)

            logger.warning("No Chrome milestone with a version found")
            return None

        except httpx.HTTPError as exc:
            logger.error("Failed to fetch Chrome releases: %s", exc)
            return None
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("Failed to parse Chrome release data: %s", exc)
            return None
