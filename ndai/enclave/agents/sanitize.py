"""Shared prompt-injection sanitization for NDAI agents.

Provides functions to escape user-controlled text before interpolation
into LLM system prompts, mitigating prompt injection attacks.
"""

import re

# Case-insensitive patterns that could hijack LLM instruction flow.
# Matches are replaced with empty string to neutralize without alerting.
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"SYSTEM\s*:",
        r"IGNORE\s+PREVIOUS",
        r"INSTRUCTIONS?\s*:",
        r"OVERRIDE",
        r"ASSISTANT\s*:",
        r"HUMAN\s*:",
        r"USER\s*:",
        r"\[INST\]",
        r"\[/INST\]",
        r"<<\s*SYS\s*>>",
        r"<</\s*SYS\s*>>",
        r"```\s*system",
        r"<\|im_start\|>",
        r"<\|im_end\|>",
        r"<\|endoftext\|>",
    ]
]

# Control characters to strip (U+0000–U+001F), keeping \n (0x0A) and \t (0x09)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def escape_for_prompt(text: str, max_length: int = 5000) -> str:
    """Sanitize user-controlled text for safe interpolation into LLM prompts.

    Steps:
        1. Truncate to max_length
        2. Replace angle brackets with HTML entities
        3. Neutralize triple backticks
        4. Strip injection patterns (case-insensitive)
        5. Strip control characters (except \\n and \\t)

    Args:
        text: Raw user-provided text.
        max_length: Maximum allowed character count.

    Returns:
        Sanitized text safe for prompt interpolation.
    """
    # 1. Truncate
    result = text[:max_length]

    # 2. Strip injection patterns (before angle bracket escaping so patterns
    #    like <<SYS>> and <|im_start|> match their raw forms)
    for pattern in _INJECTION_PATTERNS:
        result = pattern.sub("[FILTERED]", result)

    # 3. Escape angle brackets to prevent XML/tag injection
    result = result.replace("<", "&lt;").replace(">", "&gt;")

    # 4. Neutralize triple backticks (used for code fences / system blocks)
    result = result.replace("```", "'''")

    # 5. Strip control characters (keep \n and \t)
    result = _CONTROL_CHAR_RE.sub("", result)

    return result


def wrap_user_data(tag: str, content: str, max_length: int = 5000) -> str:
    """Wrap escaped user content in XML tags for clear LLM boundary marking.

    Args:
        tag: XML tag name (e.g. "invention_data", "disclosed_invention").
        content: Raw user-provided text (will be escaped).
        max_length: Maximum length passed to escape_for_prompt.

    Returns:
        String of the form ``<tag>escaped_content</tag>``.
    """
    escaped = escape_for_prompt(content, max_length=max_length)
    return f"<{tag}>{escaped}</{tag}>"
