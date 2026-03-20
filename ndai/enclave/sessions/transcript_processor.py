"""TEE session for Props meeting transcript processing."""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

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
    policy_report: dict | None = None
    policy_constraints: list[dict] | None = None
    egress_log: list[dict] | None = None
    verification: dict | None = None


class TranscriptProcessingSession:
    def __init__(self, config: TranscriptConfig):
        self.config = config

    def run(self) -> TranscriptResult:
        from ndai.enclave.egress import EgressAwareLLMClient, EgressLog
        from ndai.enclave.policy.engine import enforce_all, hash_policy
        from ndai.enclave.policy.generator import generate_policy
        from ndai.enclave.verification import SessionVerificationChain

        chain = SessionVerificationChain()
        egress_log = EgressLog()

        try:
            chain.record("session_start", {
                "title": self.config.title,
                "team_name": self.config.team_name,
            }, "Transcript processing session initialized")

            # Build LLM client with egress logging
            client = self._build_client(egress_log)

            # Generate policy
            context = f"Meeting transcript: {self.config.title}"
            if self.config.team_name:
                context += f" (Team: {self.config.team_name})"
            policy = generate_policy("props", context, client)
            chain.record("policy_generated", {
                "task_type": "props",
                "constraint_count": len(policy.constraints),
                "policy_hash": hash_policy(policy),
            }, "Policy generated for transcript processing")

            # Call LLM
            raw = self._call_llm_with_client(client)
            chain.record("llm_call", {"model": client.model}, "LLM called for transcript analysis")

            # Parse response
            parsed = self._parse_response(raw)

            # Enforce policy on parsed fields
            fields_to_check = {
                "executive_summary": parsed.executive_summary,
                "sentiment": parsed.sentiment,
            }
            policy_report = enforce_all(policy, fields_to_check)
            chain.record("policy_enforced", {
                "all_passed": policy_report.all_passed,
                "policy_hash": policy_report.policy_hash,
            }, "Policy enforced deterministically on LLM output")

            chain.record("result_produced", {
                "success": True,
                "policy_passed": policy_report.all_passed,
            }, "Result produced and validated")

            report = chain.finalize()

            parsed.policy_report = {
                "all_passed": policy_report.all_passed,
                "results": [
                    {"field": r.field, "passed": r.passed, "violations": r.violations}
                    for r in policy_report.results
                ],
                "policy_hash": policy_report.policy_hash,
            }
            parsed.policy_constraints = [
                {
                    "field": c.field,
                    "pattern": c.pattern,
                    "deny_patterns": c.deny_patterns,
                    "max_length": c.max_length,
                    "rationale": c.rationale,
                }
                for c in policy.constraints
            ]
            parsed.egress_log = egress_log.to_dict_list()
            parsed.verification = _report_to_dict(report)

            return parsed
        except Exception as e:
            logger.error("Transcript processing failed: %s", e)
            chain.record("result_produced", {"error": str(e)}, "Processing failed")
            report = chain.finalize()
            return TranscriptResult(
                success=False,
                error=str(e),
                transcript_deleted=True,
                verification=_report_to_dict(report),
            )
        finally:
            self.config.transcript_text = None
            chain.record("sensitive_data_cleared", {}, "Raw transcript deleted from session memory")
            logger.info("Raw transcript deleted from session memory")

    def _build_client(self, egress_log: Any) -> Any:
        from ndai.enclave.agents.llm_client import LLMClient
        from ndai.enclave.agents.openai_llm_client import OpenAILLMClient
        from ndai.enclave.egress import EgressAwareLLMClient

        if self.config.llm_provider == "openai":
            raw_client = OpenAILLMClient(api_key=self.config.api_key, model=self.config.llm_model)
        else:
            raw_client = LLMClient(api_key=self.config.api_key, model=self.config.llm_model)

        return EgressAwareLLMClient(raw_client, egress_log)

    def _call_llm_with_client(self, client: Any) -> str:
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


def _report_to_dict(report: Any) -> dict:
    return {
        "session_id": report.session_id,
        "events": report.events,
        "chain_hashes": report.chain_hashes,
        "final_hash": report.final_hash,
        "attestation_claims": report.attestation_claims,
    }
