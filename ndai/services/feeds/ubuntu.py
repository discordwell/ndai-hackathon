"""Ubuntu LTS release checker — returns the current latest LTS version."""

import logging

logger = logging.getLogger(__name__)

# Ubuntu LTS releases happen on a fixed 2-year cadence (April of even years).
# Since releases are infrequent and well-known, we hardcode the current latest
# and update this value when a new LTS ships.
_CURRENT_LTS_VERSION = "24.04"
_CURRENT_LTS_CODENAME = "Noble Numbat"


class UbuntuReleaseChecker:
    """Checks latest Ubuntu LTS package versions from Launchpad.

    Unlike Chrome/Firefox, Ubuntu LTS releases are infrequent (every 2 years).
    This checker returns the current known latest LTS version rather than
    querying an API, since the release schedule is fixed and predictable.
    """

    async def get_latest_version(self) -> str | None:
        """Return latest Ubuntu LTS version string.

        Returns:
            Version string (e.g. "24.04") or None on failure.
        """
        logger.info(
            "Ubuntu LTS version: %s (%s)", _CURRENT_LTS_VERSION, _CURRENT_LTS_CODENAME
        )
        return _CURRENT_LTS_VERSION
