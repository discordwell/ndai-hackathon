"""Tests for the OpenAI LLM client — format translation, response parsing,
extract_tool_use, extract_text, and _clean_messages.

All OpenAI API calls are mocked; no real network requests are made.
"""

import json
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ndai.enclave.agents.openai_llm_client import (
    ContentBlock,
    OpenAILLMClient,
    OpenAILLMError,
    OpenAIMessageWrapper,
    _parse_openai_response,
    _translate_messages_to_openai,
    _translate_tool_choice_to_openai,
    _translate_tools_to_openai,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_openai_response(
    content: str | None = None,
    tool_calls: list[dict] | None = None,
    finish_reason: str = "stop",
):
    """Build a mock OpenAI ChatCompletion response object."""
    message = SimpleNamespace(content=content, tool_calls=None)

    if tool_calls:
        tc_objects = []
        for tc in tool_calls:
            fn = SimpleNamespace(
                name=tc["name"],
                arguments=json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else tc["arguments"],
            )
            tc_objects.append(SimpleNamespace(id=tc["id"], type="function", function=fn))
        message.tool_calls = tc_objects

    choice = SimpleNamespace(message=message, finish_reason=finish_reason, index=0)
    return SimpleNamespace(choices=[choice], id="chatcmpl-test", model="gpt-4o")


# ---------------------------------------------------------------------------
# Tool format translation
# ---------------------------------------------------------------------------


class TestToolTranslation:
    def test_single_tool(self):
        anthropic_tools = [
            {
                "name": "make_disclosure",
                "description": "Disclose invention details.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string"},
                    },
                    "required": ["summary"],
                },
            }
        ]
        result = _translate_tools_to_openai(anthropic_tools)

        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "make_disclosure"
        assert result[0]["function"]["description"] == "Disclose invention details."
        assert result[0]["function"]["parameters"]["type"] == "object"
        assert "summary" in result[0]["function"]["parameters"]["properties"]

    def test_multiple_tools(self):
        tools = [
            {"name": "tool_a", "description": "A", "input_schema": {"type": "object", "properties": {}}},
            {"name": "tool_b", "description": "B", "input_schema": {"type": "object", "properties": {}}},
        ]
        result = _translate_tools_to_openai(tools)
        assert len(result) == 2
        assert result[0]["function"]["name"] == "tool_a"
        assert result[1]["function"]["name"] == "tool_b"

    def test_missing_description(self):
        tools = [{"name": "no_desc", "input_schema": {"type": "object"}}]
        result = _translate_tools_to_openai(tools)
        assert result[0]["function"]["description"] == ""

    def test_missing_input_schema(self):
        tools = [{"name": "no_schema", "description": "No schema tool"}]
        result = _translate_tools_to_openai(tools)
        assert result[0]["function"]["parameters"] == {}


# ---------------------------------------------------------------------------
# Tool choice translation
# ---------------------------------------------------------------------------


class TestToolChoiceTranslation:
    def test_specific_tool(self):
        anthropic_choice = {"type": "tool", "name": "make_disclosure"}
        result = _translate_tool_choice_to_openai(anthropic_choice)
        assert result == {"type": "function", "function": {"name": "make_disclosure"}}

    def test_auto(self):
        result = _translate_tool_choice_to_openai({"type": "auto"})
        assert result == "auto"

    def test_any(self):
        result = _translate_tool_choice_to_openai({"type": "any"})
        assert result == "required"

    def test_default_is_auto(self):
        result = _translate_tool_choice_to_openai({})
        assert result == "auto"


# ---------------------------------------------------------------------------
# Message format translation
# ---------------------------------------------------------------------------


class TestMessageTranslation:
    def test_system_message_prepended(self):
        result = _translate_messages_to_openai(
            "You are a negotiator.",
            [{"role": "user", "content": "Hello"}],
        )
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are a negotiator."
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "Hello"

    def test_empty_system_omitted(self):
        result = _translate_messages_to_openai(
            "",
            [{"role": "user", "content": "Hello"}],
        )
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_simple_user_message(self):
        result = _translate_messages_to_openai(
            "sys",
            [{"role": "user", "content": "What is this?"}],
        )
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "What is this?"

    def test_assistant_with_tool_use_content_blocks(self):
        """Anthropic assistant message with tool_use blocks -> OpenAI tool_calls."""
        messages = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me analyze this."},
                    {
                        "type": "tool_use",
                        "id": "tool_123",
                        "name": "make_disclosure",
                        "input": {"summary": "A great invention"},
                    },
                ],
            }
        ]
        result = _translate_messages_to_openai("sys", messages)

        assistant_msg = result[1]  # index 0 is system
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["content"] == "Let me analyze this."
        assert len(assistant_msg["tool_calls"]) == 1
        tc = assistant_msg["tool_calls"][0]
        assert tc["id"] == "tool_123"
        assert tc["type"] == "function"
        assert tc["function"]["name"] == "make_disclosure"
        assert json.loads(tc["function"]["arguments"]) == {"summary": "A great invention"}

    def test_tool_result_becomes_role_tool(self):
        """Anthropic tool_result in user message -> OpenAI role=tool message."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tool_123",
                        "content": [{"type": "text", "text": "Evaluation recorded."}],
                    }
                ],
            }
        ]
        result = _translate_messages_to_openai("sys", messages)

        tool_msg = result[1]  # index 0 is system
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "tool_123"
        assert tool_msg["content"] == "Evaluation recorded."

    def test_tool_result_with_string_content(self):
        """Tool result with plain string content."""
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "t1",
                        "content": "Done.",
                    }
                ],
            }
        ]
        result = _translate_messages_to_openai("", messages)
        assert result[0]["role"] == "tool"
        assert result[0]["content"] == "Done."

    def test_assistant_with_sdk_objects(self):
        """Assistant content with objects that have model_dump()."""
        block = ContentBlock(
            type="tool_use", id="sdk_01", name="make_offer", input={"price": 0.5}
        )
        messages = [
            {"role": "assistant", "content": [block]},
        ]
        result = _translate_messages_to_openai("sys", messages)

        assistant_msg = result[1]
        assert len(assistant_msg["tool_calls"]) == 1
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "make_offer"

    def test_user_message_with_text_content_blocks(self):
        """User content as list of text blocks extracts text."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Part 1"},
                    {"type": "text", "text": "Part 2"},
                ],
            }
        ]
        result = _translate_messages_to_openai("", messages)
        assert result[0]["role"] == "user"
        assert "Part 1" in result[0]["content"]
        assert "Part 2" in result[0]["content"]


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class TestResponseParsing:
    def test_text_only_response(self):
        raw = _make_openai_response(content="Hello, world!")
        wrapped = _parse_openai_response(raw)

        assert len(wrapped.content) == 1
        assert wrapped.content[0].type == "text"
        assert wrapped.content[0].text == "Hello, world!"
        assert wrapped.stop_reason == "end_turn"

    def test_tool_call_response(self):
        raw = _make_openai_response(
            content=None,
            tool_calls=[
                {
                    "id": "call_abc",
                    "name": "make_disclosure",
                    "arguments": {"summary": "Quantum protocol", "disclosed_value": 0.6},
                }
            ],
            finish_reason="tool_calls",
        )
        wrapped = _parse_openai_response(raw)

        assert len(wrapped.content) == 1
        block = wrapped.content[0]
        assert block.type == "tool_use"
        assert block.id == "call_abc"
        assert block.name == "make_disclosure"
        assert block.input == {"summary": "Quantum protocol", "disclosed_value": 0.6}
        assert wrapped.stop_reason == "tool_use"

    def test_text_and_tool_response(self):
        raw = _make_openai_response(
            content="I will disclose now.",
            tool_calls=[
                {
                    "id": "call_xyz",
                    "name": "make_disclosure",
                    "arguments": {"summary": "Test"},
                }
            ],
            finish_reason="tool_calls",
        )
        wrapped = _parse_openai_response(raw)

        assert len(wrapped.content) == 2
        assert wrapped.content[0].type == "text"
        assert wrapped.content[0].text == "I will disclose now."
        assert wrapped.content[1].type == "tool_use"
        assert wrapped.content[1].name == "make_disclosure"

    def test_invalid_json_arguments_returns_empty_dict(self):
        raw = _make_openai_response(
            tool_calls=[
                {"id": "call_bad", "name": "broken", "arguments": "not json {{{"},
            ],
            finish_reason="tool_calls",
        )
        wrapped = _parse_openai_response(raw)

        assert wrapped.content[0].type == "tool_use"
        assert wrapped.content[0].input == {}

    def test_multiple_tool_calls(self):
        raw = _make_openai_response(
            tool_calls=[
                {"id": "c1", "name": "tool_a", "arguments": {"x": 1}},
                {"id": "c2", "name": "tool_b", "arguments": {"y": 2}},
            ],
            finish_reason="tool_calls",
        )
        wrapped = _parse_openai_response(raw)

        assert len(wrapped.content) == 2
        assert wrapped.content[0].name == "tool_a"
        assert wrapped.content[1].name == "tool_b"


# ---------------------------------------------------------------------------
# extract_tool_use and extract_text
# ---------------------------------------------------------------------------


class TestExtractMethods:
    def setup_method(self):
        self.client = OpenAILLMClient.__new__(OpenAILLMClient)

    def test_extract_tool_use_found(self):
        response = OpenAIMessageWrapper(
            content=[
                ContentBlock(type="text", text="Thinking..."),
                ContentBlock(
                    type="tool_use", id="t1", name="make_offer",
                    input={"price": 0.4, "explanation": "Fair price"},
                ),
            ]
        )
        result = self.client.extract_tool_use(response)
        assert result is not None
        assert result["name"] == "make_offer"
        assert result["input"]["price"] == 0.4
        assert result["id"] == "t1"

    def test_extract_tool_use_none(self):
        response = OpenAIMessageWrapper(
            content=[ContentBlock(type="text", text="No tools here.")]
        )
        assert self.client.extract_tool_use(response) is None

    def test_extract_tool_use_empty_content(self):
        response = OpenAIMessageWrapper(content=[])
        assert self.client.extract_tool_use(response) is None

    def test_extract_text_single_block(self):
        response = OpenAIMessageWrapper(
            content=[ContentBlock(type="text", text="Hello")]
        )
        assert self.client.extract_text(response) == "Hello"

    def test_extract_text_multiple_blocks(self):
        response = OpenAIMessageWrapper(
            content=[
                ContentBlock(type="text", text="Part 1"),
                ContentBlock(type="tool_use", id="t1", name="x", input={}),
                ContentBlock(type="text", text="Part 2"),
            ]
        )
        assert self.client.extract_text(response) == "Part 1\nPart 2"

    def test_extract_text_no_text_blocks(self):
        response = OpenAIMessageWrapper(
            content=[ContentBlock(type="tool_use", id="t1", name="x", input={})]
        )
        assert self.client.extract_text(response) == ""


# ---------------------------------------------------------------------------
# _clean_messages
# ---------------------------------------------------------------------------


class TestCleanMessages:
    def test_passthrough_string_content(self):
        messages = [{"role": "user", "content": "hello"}]
        assert OpenAILLMClient._clean_messages(messages) == messages

    def test_passthrough_dict_blocks(self):
        messages = [
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "hi"}],
            }
        ]
        result = OpenAILLMClient._clean_messages(messages)
        assert result[0]["content"] == [{"type": "text", "text": "hi"}]

    def test_serializes_content_blocks(self):
        block = ContentBlock(type="tool_use", id="t1", name="foo", input={"x": 1})
        messages = [{"role": "assistant", "content": [block]}]
        result = OpenAILLMClient._clean_messages(messages)

        assert isinstance(result[0]["content"][0], dict)
        assert result[0]["content"][0]["type"] == "tool_use"
        assert result[0]["content"][0]["name"] == "foo"
        assert result[0]["content"][0]["input"] == {"x": 1}

    def test_handles_none_content(self):
        messages = [{"role": "assistant", "content": None}]
        result = OpenAILLMClient._clean_messages(messages)
        assert result[0]["content"] is None

    def test_converts_unknown_to_string(self):
        messages = [{"role": "user", "content": 42}]
        result = OpenAILLMClient._clean_messages(messages)
        assert result[0]["content"] == "42"

    def test_converts_non_dict_list_items_to_text(self):
        messages = [{"role": "user", "content": ["some string"]}]
        result = OpenAILLMClient._clean_messages(messages)
        assert result[0]["content"] == [{"type": "text", "text": "some string"}]


# ---------------------------------------------------------------------------
# ContentBlock.model_dump
# ---------------------------------------------------------------------------


class TestContentBlockModelDump:
    def test_text_block(self):
        block = ContentBlock(type="text", text="Hello")
        assert block.model_dump() == {"type": "text", "text": "Hello"}

    def test_tool_use_block(self):
        block = ContentBlock(
            type="tool_use", id="t1", name="make_offer", input={"price": 0.5}
        )
        assert block.model_dump() == {
            "type": "tool_use",
            "id": "t1",
            "name": "make_offer",
            "input": {"price": 0.5},
        }

    def test_unknown_type_block(self):
        block = ContentBlock(type="image", text="data")
        assert block.model_dump() == {"type": "image", "text": "data"}


# ---------------------------------------------------------------------------
# Full create_message integration (mocked API)
# ---------------------------------------------------------------------------


class TestCreateMessage:
    @patch("ndai.enclave.agents.openai_llm_client.openai.OpenAI")
    def test_create_message_text_response(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        raw_response = _make_openai_response(content="Understood.")
        mock_client.chat.completions.create.return_value = raw_response

        client = OpenAILLMClient(api_key="test-key", model="gpt-4o")
        result = client.create_message(
            system="You are a helper.",
            messages=[{"role": "user", "content": "Hi"}],
        )

        assert isinstance(result, OpenAIMessageWrapper)
        assert client.extract_text(result) == "Understood."
        assert client.extract_tool_use(result) is None

        # Verify the API was called with correct params
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][1]["role"] == "user"

    @patch("ndai.enclave.agents.openai_llm_client.openai.OpenAI")
    def test_create_message_with_tools(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        raw_response = _make_openai_response(
            tool_calls=[
                {
                    "id": "call_001",
                    "name": "make_disclosure",
                    "arguments": {"summary": "My invention", "disclosed_value": 0.7},
                }
            ],
            finish_reason="tool_calls",
        )
        mock_client.chat.completions.create.return_value = raw_response

        anthropic_tools = [
            {
                "name": "make_disclosure",
                "description": "Disclose details.",
                "input_schema": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                },
            }
        ]
        anthropic_tool_choice = {"type": "tool", "name": "make_disclosure"}

        client = OpenAILLMClient(api_key="test-key")
        result = client.create_message(
            system="System prompt",
            messages=[{"role": "user", "content": "Disclose now."}],
            tools=anthropic_tools,
            tool_choice=anthropic_tool_choice,
        )

        tool_use = client.extract_tool_use(result)
        assert tool_use is not None
        assert tool_use["name"] == "make_disclosure"
        assert tool_use["input"]["summary"] == "My invention"
        assert tool_use["id"] == "call_001"

        # Verify tools were translated to OpenAI format
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"][0]["type"] == "function"
        assert call_kwargs["tools"][0]["function"]["name"] == "make_disclosure"
        assert call_kwargs["tool_choice"] == {
            "type": "function",
            "function": {"name": "make_disclosure"},
        }

    @patch("ndai.enclave.agents.openai_llm_client.openai.OpenAI")
    def test_create_message_api_error(self, mock_openai_cls):
        import openai as openai_module

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = openai_module.APIStatusError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None,
        )

        client = OpenAILLMClient(api_key="test-key")
        with pytest.raises(OpenAILLMError, match="API error"):
            client.create_message(
                system="sys",
                messages=[{"role": "user", "content": "Hi"}],
            )

    @patch("ndai.enclave.agents.openai_llm_client.openai.OpenAI")
    def test_create_message_connection_error(self, mock_openai_cls):
        import openai as openai_module

        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        mock_client.chat.completions.create.side_effect = openai_module.APIConnectionError(
            request=MagicMock(),
        )

        client = OpenAILLMClient(api_key="test-key")
        with pytest.raises(OpenAILLMError, match="Connection error"):
            client.create_message(
                system="sys",
                messages=[{"role": "user", "content": "Hi"}],
            )


# ---------------------------------------------------------------------------
# Conversation round-trip (simulates agent usage pattern)
# ---------------------------------------------------------------------------


class TestConversationRoundTrip:
    """Test that a multi-turn conversation with tool_use -> tool_result works."""

    @patch("ndai.enclave.agents.openai_llm_client.openai.OpenAI")
    def test_multi_turn_with_tool_result(self, mock_openai_cls):
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client

        # First call: model returns a tool call
        first_response = _make_openai_response(
            tool_calls=[
                {"id": "call_eval", "name": "evaluate_invention", "arguments": {"assessed_value": 0.5}},
            ],
            finish_reason="tool_calls",
        )
        # Second call: model returns text
        second_response = _make_openai_response(content="Offer made.", finish_reason="stop")

        mock_client.chat.completions.create.side_effect = [first_response, second_response]

        client = OpenAILLMClient(api_key="test-key")

        # Turn 1: user sends, gets tool use back
        conversation = [{"role": "user", "content": "Evaluate the invention."}]
        resp1 = client.create_message(system="sys", messages=conversation, tools=[
            {"name": "evaluate_invention", "description": "Eval", "input_schema": {"type": "object", "properties": {}}},
        ])

        tool_use = client.extract_tool_use(resp1)
        assert tool_use is not None

        # Store assistant response in conversation (as agents do)
        conversation.append({"role": "assistant", "content": resp1.content})

        # Add tool result (Anthropic format — will be translated)
        conversation.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use["id"],
                    "content": [{"type": "text", "text": "Evaluation recorded."}],
                },
            ],
        })

        # Turn 2: cleaned messages should serialize ContentBlocks
        resp2 = client.create_message(system="sys", messages=conversation)
        assert client.extract_text(resp2) == "Offer made."

        # Verify the second API call translated messages correctly
        second_call_kwargs = mock_client.chat.completions.create.call_args_list[1].kwargs
        openai_msgs = second_call_kwargs["messages"]

        # Should have: system, user, assistant (with tool_calls), tool (result), no extra
        roles = [m["role"] for m in openai_msgs]
        assert roles[0] == "system"
        assert roles[1] == "user"
        assert roles[2] == "assistant"
        assert roles[3] == "tool"
