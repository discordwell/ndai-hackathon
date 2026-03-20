"""Tests for browser tool definitions and CDP command translation."""

import pytest
from unittest.mock import AsyncMock
from ndai.enclave.agents.browser_tools import BrowserTools, BROWSER_TOOL_DEFINITIONS


class TestToolDefinitions:
    def test_all_tools_have_names(self):
        for tool in BROWSER_TOOL_DEFINITIONS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_expected_tools_exist(self):
        names = {t["name"] for t in BROWSER_TOOL_DEFINITIONS}
        assert "navigate" in names
        assert "screenshot" in names
        assert "scrape" in names
        assert "execute_js" in names
        assert "fill_form" in names
        assert "click" in names
        assert "get_page_text" in names


class TestBrowserToolsExecution:
    @pytest.fixture
    def mock_cdp(self):
        cdp = AsyncMock()
        cdp.send_command = AsyncMock(return_value={"result": {}})
        return cdp

    @pytest.fixture
    def tools(self, mock_cdp):
        return BrowserTools(mock_cdp)

    @pytest.mark.asyncio
    async def test_navigate_sends_page_navigate(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"frameId": "1"}}
        result = await tools.navigate("https://example.com")
        mock_cdp.send_command.assert_any_call("Page.navigate", {"url": "https://example.com"})

    @pytest.mark.asyncio
    async def test_screenshot_returns_base64(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"data": "iVBORw0KGgo="}}
        result = await tools.screenshot()
        mock_cdp.send_command.assert_called_with("Page.captureScreenshot", {"format": "png"})
        assert result == "iVBORw0KGgo="

    @pytest.mark.asyncio
    async def test_execute_js(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"result": {"value": "Example"}}}
        result = await tools.execute_js("document.title")
        mock_cdp.send_command.assert_called_with(
            "Runtime.evaluate", {"expression": "document.title", "returnByValue": True}
        )

    @pytest.mark.asyncio
    async def test_get_page_text(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"result": {"value": "Hello World"}}}
        result = await tools.get_page_text()
        assert result == "Hello World"

    @pytest.mark.asyncio
    async def test_click(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"result": {"value": True}}}
        result = await tools.click("#btn")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_tool_dispatch(self, tools, mock_cdp):
        mock_cdp.send_command.return_value = {"result": {"result": {"value": "test"}}}
        result = await tools.execute_tool("get_page_text", {})
        assert result == "test"

    @pytest.mark.asyncio
    async def test_execute_tool_unknown_raises(self, tools):
        with pytest.raises(ValueError, match="Unknown browser tool"):
            await tools.execute_tool("nonexistent", {})

    @pytest.mark.asyncio
    async def test_transcript_hashing(self, mock_cdp):
        mock_transcript = AsyncMock()
        mock_transcript.add_message = lambda *a: None  # sync
        tools = BrowserTools(mock_cdp, transcript_hasher=mock_transcript)
        mock_cdp.send_command.return_value = {"result": {"result": {"value": "text"}}}
        await tools.execute_tool("get_page_text", {})
        # Just verify it doesn't crash with a transcript hasher
