"""Unit tests for target auto-updater and feed checkers."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ndai.models.known_target import KnownTarget, TargetBuild
from ndai.services.feeds.chrome import ChromeReleaseChecker
from ndai.services.feeds.firefox import FirefoxReleaseChecker
from ndai.services.feeds.ubuntu import UbuntuReleaseChecker
from ndai.services.target_updater import TargetUpdater, _get_checker_for_slug


# ── Chrome Feed Checker ──


class TestChromeReleaseChecker:
    @pytest.mark.asyncio
    async def test_parses_milestones_response(self):
        """ChromeReleaseChecker correctly extracts version from milestones API."""
        sample_response = [
            {
                "milestone": 125,
                "version": "125.0.6422.60",
                "chromium_main_branch_position": 1313161,
            },
            {
                "milestone": 124,
                "version": "124.0.6367.91",
                "chromium_main_branch_position": 1300000,
            },
            {
                "milestone": 123,
                "version": "123.0.6312.122",
                "chromium_main_branch_position": 1287000,
            },
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = sample_response
        mock_response.raise_for_status = MagicMock()

        checker = ChromeReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version == "125.0.6422.60"

    @pytest.mark.asyncio
    async def test_returns_none_on_empty_response(self):
        """ChromeReleaseChecker returns None when API returns empty list."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        checker = ChromeReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        """ChromeReleaseChecker returns None when HTTP request fails."""
        checker = ChromeReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Server Error",
                    request=MagicMock(),
                    response=MagicMock(status_code=500),
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version is None

    @pytest.mark.asyncio
    async def test_skips_milestones_without_version(self):
        """ChromeReleaseChecker skips milestones that lack a version field."""
        sample_response = [
            {"milestone": 126},  # No version field
            {"milestone": 125, "version": "125.0.6422.60"},
        ]

        mock_response = MagicMock()
        mock_response.json.return_value = sample_response
        mock_response.raise_for_status = MagicMock()

        checker = ChromeReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version == "125.0.6422.60"


# ── Firefox Feed Checker ──


class TestFirefoxReleaseChecker:
    @pytest.mark.asyncio
    async def test_parses_firefox_versions_response(self):
        """FirefoxReleaseChecker correctly extracts LATEST_FIREFOX_VERSION."""
        sample_response = {
            "LATEST_FIREFOX_VERSION": "125.0.1",
            "LATEST_FIREFOX_DEVEL_VERSION": "126.0b5",
            "LATEST_FIREFOX_RELEASED_DEVEL_VERSION": "126.0b5",
            "FIREFOX_ESR": "115.10.0esr",
            "FIREFOX_ESR_NEXT": "",
            "LATEST_FIREFOX_OLDER_VERSION": "3.6.28",
            "FIREFOX_NIGHTLY": "127.0a1",
            "FIREFOX_DEVEDITION": "126.0b5",
        }

        mock_response = MagicMock()
        mock_response.json.return_value = sample_response
        mock_response.raise_for_status = MagicMock()

        checker = FirefoxReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version == "125.0.1"

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_key(self):
        """FirefoxReleaseChecker returns None when expected key is absent."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"FIREFOX_NIGHTLY": "127.0a1"}
        mock_response.raise_for_status = MagicMock()

        checker = FirefoxReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version is None

    @pytest.mark.asyncio
    async def test_returns_none_on_http_error(self):
        """FirefoxReleaseChecker returns None when HTTP request fails."""
        checker = FirefoxReleaseChecker()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.HTTPStatusError(
                    "Not Found",
                    request=MagicMock(),
                    response=MagicMock(status_code=404),
                )
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            version = await checker.get_latest_version()

        assert version is None


# ── Ubuntu Release Checker ──


class TestUbuntuReleaseChecker:
    @pytest.mark.asyncio
    async def test_returns_known_lts_version(self):
        """UbuntuReleaseChecker returns the hardcoded latest LTS version."""
        checker = UbuntuReleaseChecker()
        version = await checker.get_latest_version()
        assert version == "24.04"

    @pytest.mark.asyncio
    async def test_returns_string(self):
        """UbuntuReleaseChecker return value is a string."""
        checker = UbuntuReleaseChecker()
        version = await checker.get_latest_version()
        assert isinstance(version, str)


# ── Checker slug routing ──


class TestCheckerRouting:
    def test_chrome_slug_matches(self):
        checker = _get_checker_for_slug("chrome-linux")
        assert isinstance(checker, ChromeReleaseChecker)

    def test_chromium_slug_matches(self):
        checker = _get_checker_for_slug("chromium-ubuntu")
        assert isinstance(checker, ChromeReleaseChecker)

    def test_firefox_slug_matches(self):
        checker = _get_checker_for_slug("firefox-linux")
        assert isinstance(checker, FirefoxReleaseChecker)

    def test_ubuntu_slug_matches(self):
        checker = _get_checker_for_slug("ubuntu-lts")
        assert isinstance(checker, UbuntuReleaseChecker)

    def test_unknown_slug_returns_none(self):
        checker = _get_checker_for_slug("windows-server")
        assert checker is None


# ── Target Updater ──


def _make_target(**kwargs):
    """Helper to construct a KnownTarget with sensible defaults."""
    defaults = dict(
        id=uuid.uuid4(),
        slug="chrome-linux",
        display_name="Google Chrome (Linux)",
        platform="linux",
        current_version="124.0.6367.91",
        verification_method="nitro",
        base_image="ubuntu:22.04",
        poc_script_type="html",
        poc_instructions="Submit an HTML exploit.",
        escrow_amount_usd=100,
        is_active=True,
    )
    defaults.update(kwargs)
    return KnownTarget(**defaults)


class TestTargetUpdater:
    @pytest.mark.asyncio
    async def test_check_target_detects_version_change(self):
        """TargetUpdater.check_target updates version when upstream is newer."""
        target = _make_target(current_version="124.0.6367.91")

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # add() is sync on AsyncSession
        # Mock the query for old builds to supersede
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        updater = TargetUpdater()

        with patch(
            "ndai.services.target_updater._get_checker_for_slug"
        ) as mock_get_checker:
            mock_checker = AsyncMock()
            mock_checker.get_latest_version = AsyncMock(return_value="125.0.6422.60")
            mock_get_checker.return_value = mock_checker

            result = await updater.check_target(target, mock_db)

        assert result is not None
        assert result["slug"] == "chrome-linux"
        assert result["old_version"] == "124.0.6367.91"
        assert result["new_version"] == "125.0.6422.60"
        assert target.current_version == "125.0.6422.60"
        mock_db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_check_target_no_change_when_current(self):
        """TargetUpdater.check_target returns None when version is already current."""
        target = _make_target(current_version="124.0.6367.91")

        mock_db = AsyncMock()

        updater = TargetUpdater()

        with patch(
            "ndai.services.target_updater._get_checker_for_slug"
        ) as mock_get_checker:
            mock_checker = AsyncMock()
            mock_checker.get_latest_version = AsyncMock(return_value="124.0.6367.91")
            mock_get_checker.return_value = mock_checker

            result = await updater.check_target(target, mock_db)

        assert result is None
        assert target.current_version == "124.0.6367.91"

    @pytest.mark.asyncio
    async def test_check_target_skips_unknown_slug(self):
        """TargetUpdater.check_target returns None for targets without a feed checker."""
        target = _make_target(slug="windows-server")

        mock_db = AsyncMock()

        updater = TargetUpdater()
        result = await updater.check_target(target, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_target_handles_feed_failure(self):
        """TargetUpdater.check_target returns None when feed returns None."""
        target = _make_target(current_version="124.0.6367.91")

        mock_db = AsyncMock()

        updater = TargetUpdater()

        with patch(
            "ndai.services.target_updater._get_checker_for_slug"
        ) as mock_get_checker:
            mock_checker = AsyncMock()
            mock_checker.get_latest_version = AsyncMock(return_value=None)
            mock_get_checker.return_value = mock_checker

            result = await updater.check_target(target, mock_db)

        assert result is None
        # Version should remain unchanged
        assert target.current_version == "124.0.6367.91"

    @pytest.mark.asyncio
    async def test_check_target_updates_last_check_timestamp(self):
        """TargetUpdater.check_target sets last_version_check even if version unchanged."""
        target = _make_target(current_version="124.0.6367.91")
        assert target.last_version_check is None

        mock_db = AsyncMock()

        updater = TargetUpdater()

        with patch(
            "ndai.services.target_updater._get_checker_for_slug"
        ) as mock_get_checker:
            mock_checker = AsyncMock()
            mock_checker.get_latest_version = AsyncMock(return_value="124.0.6367.91")
            mock_get_checker.return_value = mock_checker

            await updater.check_target(target, mock_db)

        assert target.last_version_check is not None
        assert isinstance(target.last_version_check, datetime)

    @pytest.mark.asyncio
    async def test_trigger_rebuild_creates_build_record(self):
        """_trigger_rebuild creates a TargetBuild with status 'building'."""
        target = _make_target()

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # add() is sync on AsyncSession
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        updater = TargetUpdater()
        await updater._trigger_rebuild(target, "125.0.6422.60", mock_db)

        mock_db.add.assert_called_once()
        build_arg = mock_db.add.call_args[0][0]
        assert isinstance(build_arg, TargetBuild)
        assert build_arg.version == "125.0.6422.60"
        assert build_arg.status == "building"
        assert build_arg.target_id == target.id

    @pytest.mark.asyncio
    async def test_trigger_rebuild_supersedes_old_builds(self):
        """_trigger_rebuild marks old ready builds as superseded."""
        target = _make_target()

        old_build = TargetBuild(
            target_id=target.id,
            version="123.0",
            build_type="eif",
            cache_key="old_key",
            artifact_path="/old/path.eif",
            status="ready",
        )

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # add() is sync on AsyncSession
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [old_build]
        mock_db.execute = AsyncMock(return_value=mock_result)

        updater = TargetUpdater()
        await updater._trigger_rebuild(target, "125.0.6422.60", mock_db)

        assert old_build.status == "superseded"

    @pytest.mark.asyncio
    async def test_check_all_aggregates_results(self):
        """TargetUpdater.check_all returns list of all updates applied."""
        updater = TargetUpdater()

        chrome = _make_target(slug="chrome-linux", current_version="124.0")
        firefox = _make_target(slug="firefox-linux", current_version="125.0")

        mock_db = AsyncMock()
        mock_db.add = MagicMock()  # add() is sync on AsyncSession

        # Mock the initial query returning targets
        mock_all_result = MagicMock()
        mock_all_result.scalars.return_value.all.return_value = [chrome, firefox]

        # Mock the supersede query (no old builds)
        mock_empty_result = MagicMock()
        mock_empty_result.scalars.return_value.all.return_value = []

        # First call returns targets, subsequent calls return empty builds
        mock_db.execute = AsyncMock(
            side_effect=[mock_all_result, mock_empty_result, mock_empty_result]
        )

        with patch(
            "ndai.services.target_updater._get_checker_for_slug"
        ) as mock_get_checker:
            mock_chrome_checker = AsyncMock()
            mock_chrome_checker.get_latest_version = AsyncMock(return_value="125.0")

            mock_firefox_checker = AsyncMock()
            mock_firefox_checker.get_latest_version = AsyncMock(return_value="126.0")

            def side_effect(slug):
                if slug.startswith("chrome"):
                    return mock_chrome_checker
                elif slug.startswith("firefox"):
                    return mock_firefox_checker
                return None

            mock_get_checker.side_effect = side_effect

            updates = await updater.check_all(mock_db)

        assert len(updates) == 2
        slugs = {u["slug"] for u in updates}
        assert "chrome-linux" in slugs
        assert "firefox-linux" in slugs
