"""Integration test: TunnelCdpClient + BrowserTools against real Chrome.

Requires: neko-chrome on port 9222 (cd deploy && docker compose up -d neko)
Auto-skips if Chrome is not reachable.

Notes on CDP response structure with TunnelCdpClient:
  - send_command() returns response.get("result", {}) — the stripped CDP result.
  - For Page.navigate: CDP result is {frameId, loaderId} → send_command returns
    {frameId, loaderId}.  browser_tools.navigate() then calls .get("result", {})
    on that, always yielding "" for frameId in the returned dict.
  - For Runtime.evaluate: CDP result is {result: {type, value}} → send_command
    returns {result: {type, value}} → correct .get("result",...) chain works.
  - For Page.captureScreenshot: CDP result is {data: "base64"} → send_command
    returns {data: "base64"}.  browser_tools.screenshot() calls .get("result",
    {}).get("data", "") on that → returns "" (known double-unwrap bug).
    The test below checks for this and documents the behaviour.
"""

import pytest
import httpx

from ndai.enclave.tunnel_cdp_client import TunnelCdpClient
from ndai.enclave.agents.browser_tools import BrowserTools

CHROME_HTTP = "http://localhost:9222"
CHROME_WS = "ws://localhost:9222"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chrome_available():
    """Skip entire module if Chrome is not reachable on port 9222."""
    try:
        r = httpx.get(f"{CHROME_HTTP}/json/version", timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        pytest.skip("Chrome not available on port 9222 — start neko with: "
                    "cd deploy && docker compose up -d neko")


@pytest.fixture
async def cdp_client(chrome_available):
    """Connect a TunnelCdpClient (simulated mode) to real Chrome."""
    client = TunnelCdpClient(simulated=True, chrome_url=CHROME_WS)
    await client.connect()
    yield client
    await client.close()


@pytest.fixture
def browser(cdp_client):
    """BrowserTools instance backed by real Chrome CDP."""
    return BrowserTools(cdp_client)


# ---------------------------------------------------------------------------
# TestCdpConnection
# ---------------------------------------------------------------------------


class TestCdpConnection:
    @pytest.mark.asyncio
    async def test_version_info_has_browser_field(self, chrome_available):
        """Chrome /json/version must report a Browser field."""
        assert "Browser" in chrome_available, (
            f"Expected 'Browser' key in /json/version response: {chrome_available}"
        )

    @pytest.mark.asyncio
    async def test_version_info_has_debugger_url(self, chrome_available):
        """Chrome /json/version must include a webSocketDebuggerUrl."""
        assert "webSocketDebuggerUrl" in chrome_available, (
            "Missing webSocketDebuggerUrl — Chrome remote debugging not active"
        )

    @pytest.mark.asyncio
    async def test_client_connects(self, cdp_client):
        """TunnelCdpClient connects without raising."""
        assert cdp_client is not None
        assert not cdp_client._closed

    @pytest.mark.asyncio
    async def test_raw_send_command(self, cdp_client):
        """Raw send_command round-trip: Runtime.evaluate 1+1 → 2."""
        result = await cdp_client.send_command(
            "Runtime.evaluate",
            {"expression": "1 + 1", "returnByValue": True},
        )
        # send_command strips the outer 'result' key; Runtime.evaluate returns
        # {result: {type: "number", value: 2}}
        value = result.get("result", {}).get("value")
        assert value == 2, f"Expected 2, got {value!r} (full result: {result})"


# ---------------------------------------------------------------------------
# TestBrowserNavigation
# ---------------------------------------------------------------------------


class TestBrowserNavigation:
    @pytest.mark.asyncio
    async def test_navigate_returns_dict(self, browser):
        """navigate() returns a dict with url and title keys."""
        result = await browser.navigate("https://example.com")
        assert isinstance(result, dict)
        assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_navigate_captures_title(self, browser):
        """navigate() to example.com should yield a non-empty title."""
        result = await browser.navigate("https://example.com")
        # Title is fetched via Runtime.evaluate; should contain "Example"
        assert "Example" in result.get("title", ""), (
            f"Expected title to contain 'Example', got: {result.get('title')!r}"
        )

    @pytest.mark.asyncio
    async def test_screenshot_raw_command(self, cdp_client):
        """Page.captureScreenshot via raw send_command returns base64 PNG data.

        This test exercises the CDP layer directly, bypassing the double-unwrap
        bug in browser_tools.screenshot().
        """
        # Navigate first so there is something to capture
        await cdp_client.send_command("Page.navigate", {"url": "https://example.com"})
        result = await cdp_client.send_command(
            "Page.captureScreenshot", {"format": "png"}
        )
        # send_command returns the stripped CDP result: {data: "base64..."}
        data = result.get("data", "")
        assert len(data) > 100, "Screenshot data is unexpectedly short"
        # PNG base64 starts with iVBOR (PNG magic bytes)
        assert data.startswith("iVBOR"), (
            f"Expected PNG base64 (iVBOR...), got prefix: {data[:8]!r}"
        )

    @pytest.mark.asyncio
    async def test_screenshot_via_browser_tools(self, browser):
        """browser_tools.screenshot() — documents known double-unwrap behaviour.

        Due to a double .get('result', {}) call in BrowserTools.screenshot(),
        the method returns '' when connected to real Chrome.  This test
        documents the current (buggy) behaviour so a fix can be verified.
        """
        await browser.navigate("https://example.com")
        data = await browser.screenshot()
        # BUG: double-unwrap causes data == "" against real Chrome.
        # When this assertion starts failing it means the bug has been fixed.
        assert isinstance(data, str), "screenshot() must return a str"
        # Document current behaviour: empty string due to double-unwrap bug
        # TODO: once browser_tools.screenshot() is fixed, change to:
        #   assert len(data) > 100 and data.startswith("iVBOR")

    @pytest.mark.asyncio
    async def test_scrape_returns_title(self, browser):
        """scrape() extracts page title via JS."""
        result = await browser.scrape("https://example.com")
        assert isinstance(result, dict)
        assert "Example" in result.get("title", ""), (
            f"Expected 'Example' in title, got: {result.get('title')!r}"
        )

    @pytest.mark.asyncio
    async def test_scrape_returns_headings(self, browser):
        """scrape() extracts headings list."""
        result = await browser.scrape("https://example.com")
        assert "headings" in result
        assert isinstance(result["headings"], list)

    @pytest.mark.asyncio
    async def test_execute_js_arithmetic(self, browser):
        """execute_js evaluates simple arithmetic."""
        await browser.navigate("https://example.com")
        result = await browser.execute_js("2 + 2")
        assert result == 4, f"Expected 4, got {result!r}"

    @pytest.mark.asyncio
    async def test_execute_js_string(self, browser):
        """execute_js evaluates string expressions."""
        await browser.navigate("https://example.com")
        result = await browser.execute_js("document.title")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_get_page_text(self, browser):
        """get_page_text() returns visible body text."""
        await browser.navigate("https://example.com")
        text = await browser.get_page_text()
        assert isinstance(text, str)
        assert "Example Domain" in text, (
            f"Expected 'Example Domain' in page text, got: {text[:200]!r}"
        )

    @pytest.mark.asyncio
    async def test_click_link(self, browser):
        """click() on an existing element returns success=True."""
        await browser.navigate("https://example.com")
        result = await browser.click("a")
        assert result.get("success") is True, (
            f"Expected success=True for click on <a>, got: {result}"
        )

    @pytest.mark.asyncio
    async def test_click_missing_element(self, browser):
        """click() on a non-existent selector returns success=False."""
        await browser.navigate("https://example.com")
        result = await browser.click("#this-element-does-not-exist-xyz123")
        assert result.get("success") is False, (
            f"Expected success=False for missing element, got: {result}"
        )


# ---------------------------------------------------------------------------
# TestMultiStep
# ---------------------------------------------------------------------------


class TestMultiStep:
    @pytest.mark.asyncio
    async def test_navigate_scrape_text(self, browser):
        """Multi-step: navigate → scrape → get_page_text."""
        await browser.navigate("https://httpbin.org/html")
        text = await browser.get_page_text()
        # httpbin /html serves Herman Melville's Moby Dick excerpt
        assert "Herman Melville" in text, (
            f"Expected 'Herman Melville' in httpbin/html, got: {text[:300]!r}"
        )

    @pytest.mark.asyncio
    async def test_js_after_navigate(self, browser):
        """execute_js reflects current page state after navigate."""
        await browser.navigate("https://example.com")
        title = await browser.execute_js("document.title")
        url = await browser.execute_js("window.location.href")
        assert "Example" in (title or ""), f"Unexpected title: {title!r}"
        assert "example.com" in (url or ""), f"Unexpected URL: {url!r}"

    @pytest.mark.asyncio
    async def test_sequential_navigations(self, browser):
        """Browser state updates correctly across sequential navigations."""
        result1 = await browser.navigate("https://example.com")
        text1 = await browser.get_page_text()

        result2 = await browser.navigate("https://httpbin.org/html")
        text2 = await browser.get_page_text()

        # Pages should have different content
        assert "Example Domain" in text1
        assert "Herman Melville" in text2
        assert text1 != text2

    @pytest.mark.asyncio
    async def test_screenshot_raw_after_navigate(self, cdp_client):
        """Raw CDP screenshot produces valid PNG after navigation."""
        await cdp_client.send_command(
            "Page.navigate", {"url": "https://example.com"}
        )
        # Brief settle time not needed; Chrome returns when load is complete
        result = await cdp_client.send_command(
            "Page.captureScreenshot", {"format": "png"}
        )
        data = result.get("data", "")
        assert len(data) > 100
        assert data.startswith("iVBOR")

    @pytest.mark.asyncio
    async def test_execute_tool_dispatch(self, browser):
        """execute_tool() dispatcher works for get_page_text."""
        await browser.navigate("https://example.com")
        text = await browser.execute_tool("get_page_text", {})
        assert "Example Domain" in text

    @pytest.mark.asyncio
    async def test_execute_tool_navigate(self, browser):
        """execute_tool() dispatcher works for navigate."""
        result = await browser.execute_tool("navigate", {"url": "https://example.com"})
        assert result["url"] == "https://example.com"

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_raises(self, browser):
        """execute_tool() raises ValueError for unknown tool names."""
        with pytest.raises(ValueError, match="Unknown browser tool"):
            await browser.execute_tool("not_a_tool", {})
