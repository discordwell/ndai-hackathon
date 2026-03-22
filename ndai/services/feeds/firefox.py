"""Firefox release feed checker — fetches latest stable version from Mozilla product details."""

import logging

import httpx

logger = logging.getLogger(__name__)


class FirefoxReleaseChecker:
    """Checks latest Firefox stable version from Mozilla product details."""

    FEED_URL = "https://product-details.mozilla.org/1.0/firefox_versions.json"

    async def get_latest_version(self) -> str | None:
        """Fetch latest stable Firefox version.

        Queries Mozilla's product-details API and extracts the
        LATEST_FIREFOX_VERSION field.

        Returns:
            Version string (e.g. "125.0.1") or None on failure.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(self.FEED_URL)
                resp.raise_for_status()

            data = resp.json()
            version = data.get("LATEST_FIREFOX_VERSION")
            if not version:
                logger.warning("Firefox feed missing LATEST_FIREFOX_VERSION key")
                return None

            logger.info("Latest Firefox stable version: %s", version)
            return str(version)

        except httpx.HTTPError as exc:
            logger.error("Failed to fetch Firefox releases: %s", exc)
            return None
        except (ValueError, KeyError, TypeError) as exc:
            logger.error("Failed to parse Firefox release data: %s", exc)
            return None
