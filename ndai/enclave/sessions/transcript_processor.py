"""TEE session for Props meeting transcript processing."""

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TranscriptConfig:
    transcript_text: str | None
    title: str
    team_name: str | None = None
    llm_provider: str = "openai"
    api_key: str = ""
    llm_model: str = "gpt-4o"


@dataclass
class TranscriptResult:
    success: bool
    executive_summary: str = ""
    action_items: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    transcript_deleted: bool = False
    error: str | None = None


class TranscriptProcessingSession:
    def __init__(self, config: TranscriptConfig):
        self.config = config

    def run(self) -> TranscriptResult:
        try:
            raw = self._call_llm()
            parsed = self._parse_response(raw)
            return parsed
        except Exception as e:
            logger.error("Transcript processing failed: %s", e)
            return TranscriptResult(success=False, error=str(e), transcript_deleted=True)
        finally:
            self.config.transcript_text = None
            logger.info("Raw transcript deleted from session memory")

    def _call_llm(self) -> str:
        from ndai.enclave.agents.llm_client import LLMClient
        from ndai.enclave.agents.openai_llm_client import OpenAILLMClient

        if self.config.llm_provider == "openai":
            client = OpenAILLMClient(api_key=self.config.api_key, model=self.config.llm_model)
        else:
            client = LLMClient(api_key=self.config.api_key, model=self.config.llm_model)

        system_prompt = (
            "You are analyzing a meeting transcript inside a Trusted Execution Environment. "
            "The raw transcript will be destroyed after processing. "
            "Extract the following and return ONLY valid JSON (no markdown, no code fences):\n"
            "{\n"
            '  "executive_summary": "2-3 sentence summary",\n'
            '  "action_items": ["person: action item", ...],\n'
            '  "key_decisions": ["decision made", ...],\n'
            '  "dependencies": ["things this team depends on from others", ...],\n'
            '  "blockers": ["things blocking progress", ...],\n'
            '  "sentiment": "positive" | "neutral" | "negative"\n'
            "}"
        )
        team_ctx = f" (Team: {self.config.team_name})" if self.config.team_name else ""
        user_prompt = f"Meeting: {self.config.title}{team_ctx}\n\nTranscript:\n{self.config.transcript_text}"

        response = client.create_message(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return client.extract_text(response)

    def _parse_response(self, raw: str) -> TranscriptResult:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return TranscriptResult(
                success=True,
                executive_summary=raw[:500],
                transcript_deleted=True,
            )

        return TranscriptResult(
            success=True,
            executive_summary=data.get("executive_summary", ""),
            action_items=data.get("action_items", []),
            key_decisions=data.get("key_decisions", []),
            dependencies=data.get("dependencies", []),
            blockers=data.get("blockers", []),
            sentiment=data.get("sentiment", "neutral"),
            transcript_deleted=True,
        )
