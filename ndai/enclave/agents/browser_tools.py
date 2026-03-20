"""High-level browser tools for evaluator agents, backed by CDP.

Provides BROWSER_TOOL_DEFINITIONS (OpenAI/Claude tool-use format) and
BrowserTools, which dispatches tool calls to CDP commands via TunnelCdpClient.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definitions (OpenAI / Claude tool-use format)
# ---------------------------------------------------------------------------

BROWSER_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "navigate",
        "description": "Navigate the browser to a URL and return the page title.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to.",
                },
            },
            "required": ["url"],
        },
    },
    {
        "name": "screenshot",
        "description": (
            "Capture a PNG screenshot of the current page. "
            "Returns a base64-encoded PNG string."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Optional URL to navigate to before taking the screenshot.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "scrape",
        "description": (
            "Extract structured DOM content from the current page. "
            "Returns title, headings, links, and visible text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Optional URL to navigate to before scraping.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "execute_js",
        "description": "Execute a JavaScript expression in the page context and return the result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "JavaScript expression to evaluate.",
                },
            },
            "required": ["script"],
        },
    },
    {
        "name": "fill_form",
        "description": "Fill form fields and optionally click a submit button.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fields": {
                    "type": "object",
                    "description": "Mapping of CSS selector -> value to fill into each field.",
                    "additionalProperties": {"type": "string"},
                },
                "submit_selector": {
                    "type": "string",
                    "description": "CSS selector for the submit button (optional).",
                },
            },
            "required": ["fields"],
        },
    },
    {
        "name": "click",
        "description": "Click an element identified by a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the element to click.",
                },
            },
            "required": ["selector"],
        },
    },
    {
        "name": "get_page_text",
        "description": "Return the visible text content of the current page (document.body.innerText).",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# BrowserTools class
# ---------------------------------------------------------------------------

class BrowserTools:
    """High-level browser operations backed by a TunnelCdpClient.

    Each method maps to one or more CDP commands.  The optional
    ``transcript_hasher`` receives (tool_name, result) pairs so browser
    actions can be included in the tamper-evident negotiation transcript.

    Usage::

        cdp = TunnelCdpClient(simulated=True)
        await cdp.connect()
        tools = BrowserTools(cdp)
        text = await tools.get_page_text()
        await cdp.close()
    """

    def __init__(self, cdp_client: Any, transcript_hasher: Any = None) -> None:
        self._cdp = cdp_client
        self._transcript_hasher = transcript_hasher

    # ------------------------------------------------------------------
    # Public dispatch
    # ------------------------------------------------------------------

    async def execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> Any:
        """Dispatch a tool call by name, hash result into transcript if configured.

        Args:
            tool_name: One of the names in BROWSER_TOOL_DEFINITIONS.
            tool_input: Arguments dict matching the tool's input_schema.

        Returns:
            The tool result (string, dict, etc.).

        Raises:
            ValueError: If tool_name is not a known browser tool.
        """
        dispatch: dict[str, Any] = {
            "navigate": lambda: self.navigate(tool_input["url"]),
            "screenshot": lambda: self.screenshot(tool_input.get("url")),
            "scrape": lambda: self.scrape(tool_input.get("url")),
            "execute_js": lambda: self.execute_js(tool_input["script"]),
            "fill_form": lambda: self.fill_form(
                tool_input["fields"],
                tool_input.get("submit_selector"),
            ),
            "click": lambda: self.click(tool_input["selector"]),
            "get_page_text": lambda: self.get_page_text(),
        }

        if tool_name not in dispatch:
            raise ValueError(f"Unknown browser tool: {tool_name!r}")

        result = await dispatch[tool_name]()

        if self._transcript_hasher is not None:
            self._transcript_hasher.add_message(
                {"tool": tool_name, "input": tool_input, "result": result}
            )

        return result

    # ------------------------------------------------------------------
    # Individual tool implementations
    # ------------------------------------------------------------------

    async def navigate(self, url: str) -> dict[str, Any]:
        """Navigate to ``url`` and return frame info + page title.

        Sends Page.navigate then evaluates document.title.
        """
        nav_response = await self._cdp.send_command("Page.navigate", {"url": url})
        nav_result = nav_response.get("result", {})

        # Best-effort: fetch title after navigation
        try:
            title_response = await self._cdp.send_command(
                "Runtime.evaluate",
                {"expression": "document.title", "returnByValue": True},
            )
            title = title_response.get("result", {}).get("result", {}).get("value", "")
        except Exception:
            title = ""

        return {"url": url, "frameId": nav_result.get("frameId", ""), "title": title}

    async def screenshot(self, url: str | None = None) -> str:
        """Return a base64-encoded PNG screenshot of the current page.

        If ``url`` is provided, navigate there first.
        """
        if url:
            await self.navigate(url)

        response = await self._cdp.send_command(
            "Page.captureScreenshot", {"format": "png"}
        )
        return response.get("result", {}).get("data", "")

    async def scrape(self, url: str | None = None) -> dict[str, Any]:
        """Extract structured DOM content from the current page.

        Returns a dict with title, headings, links, and text.
        If ``url`` is provided, navigate there first.
        """
        if url:
            await self.navigate(url)

        dom_js = """(function() {
            var headings = Array.from(document.querySelectorAll('h1,h2,h3'))
                .map(function(h) { return h.innerText.trim(); })
                .filter(Boolean);
            var links = Array.from(document.querySelectorAll('a[href]'))
                .map(function(a) { return {text: a.innerText.trim(), href: a.href}; })
                .filter(function(l) { return l.text; });
            return JSON.stringify({
                title: document.title,
                headings: headings,
                links: links.slice(0, 50),
                text: (document.body && document.body.innerText)
                    ? document.body.innerText.substring(0, 4000)
                    : ''
            });
        })()"""

        response = await self._cdp.send_command(
            "Runtime.evaluate",
            {"expression": dom_js, "returnByValue": True},
        )

        import json as _json
        raw = response.get("result", {}).get("result", {}).get("value", "{}")
        try:
            return _json.loads(raw)
        except Exception:
            return {"raw": raw}

    async def execute_js(self, script: str) -> Any:
        """Evaluate ``script`` in the page context and return its value."""
        response = await self._cdp.send_command(
            "Runtime.evaluate",
            {"expression": script, "returnByValue": True},
        )
        return response.get("result", {}).get("result", {}).get("value")

    async def fill_form(
        self,
        fields: dict[str, str],
        submit_selector: str | None = None,
    ) -> dict[str, Any]:
        """Fill form fields and optionally click a submit button.

        Args:
            fields: {css_selector: value} mapping.
            submit_selector: CSS selector for the submit element (optional).

        Returns:
            Dict with filled_count and submit_clicked.
        """
        filled = 0
        for selector, value in fields.items():
            # Escape selector and value for safe injection into JS string
            safe_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
            safe_value = value.replace("\\", "\\\\").replace("'", "\\'")
            fill_js = (
                f"(function() {{"
                f"  var el = document.querySelector('{safe_selector}');"
                f"  if (!el) return false;"
                f"  el.value = '{safe_value}';"
                f"  el.dispatchEvent(new Event('input', {{bubbles: true}}));"
                f"  el.dispatchEvent(new Event('change', {{bubbles: true}}));"
                f"  return true;"
                f"}})();"
            )
            response = await self._cdp.send_command(
                "Runtime.evaluate",
                {"expression": fill_js, "returnByValue": True},
            )
            if response.get("result", {}).get("result", {}).get("value"):
                filled += 1
            else:
                logger.warning("fill_form: selector %r not found", selector)

        submit_clicked = False
        if submit_selector:
            safe_sub = submit_selector.replace("\\", "\\\\").replace("'", "\\'")
            submit_js = (
                f"(function() {{"
                f"  var el = document.querySelector('{safe_sub}');"
                f"  if (!el) return false;"
                f"  el.click();"
                f"  return true;"
                f"}})();"
            )
            res = await self._cdp.send_command(
                "Runtime.evaluate",
                {"expression": submit_js, "returnByValue": True},
            )
            submit_clicked = bool(res.get("result", {}).get("result", {}).get("value"))

        return {"filled_count": filled, "submit_clicked": submit_clicked}

    async def click(self, selector: str) -> dict[str, Any]:
        """Click an element identified by ``selector``.

        Returns:
            Dict with ``success`` bool and optional ``error`` message.
        """
        safe_selector = selector.replace("\\", "\\\\").replace("'", "\\'")
        click_js = (
            f"(function() {{"
            f"  var el = document.querySelector('{safe_selector}');"
            f"  if (!el) return false;"
            f"  el.click();"
            f"  return true;"
            f"}})();"
        )
        response = await self._cdp.send_command(
            "Runtime.evaluate",
            {"expression": click_js, "returnByValue": True},
        )
        success = bool(response.get("result", {}).get("result", {}).get("value"))
        return {"success": success, "selector": selector}

    async def get_page_text(self) -> str:
        """Return ``document.body.innerText`` of the current page."""
        response = await self._cdp.send_command(
            "Runtime.evaluate",
            {"expression": "document.body.innerText", "returnByValue": True},
        )
        return response.get("result", {}).get("result", {}).get("value", "")
