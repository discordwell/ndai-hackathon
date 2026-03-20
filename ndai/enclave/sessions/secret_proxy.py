"""TEE session for Conditional Recall credential proxy."""

import logging
from dataclasses import dataclass, field as dataclass_field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SecretProxyConfig:
    secret_value: str | None
    action: str
    policy: dict
    llm_provider: str = "openai"
    api_key: str = ""
    llm_model: str = "gpt-4o"


@dataclass
class SecretProxyResult:
    success: bool
    result_text: str
    action_validated: bool
    secret_deleted: bool
    policy_report: dict | None = None
    policy_constraints: list[dict] | None = None
    egress_log: list[dict] | None = None
    verification: dict | None = None


class SecretProxySession:
    def __init__(self, config: SecretProxyConfig):
        self.config = config

    def run(self) -> SecretProxyResult:
        from ndai.enclave.egress import EgressAwareLLMClient, EgressLog
        from ndai.enclave.policy.engine import enforce_all, hash_policy
        from ndai.enclave.policy.generator import generate_policy
        from ndai.enclave.verification import SessionVerificationChain

        chain = SessionVerificationChain()
        egress_log = EgressLog()

        try:
            chain.record("session_start", {
                "action": self.config.action,
                "policy_actions": self.config.policy.get("allowed_actions", []),
            }, "Recall session initialized")

            allowed = self.config.policy.get("allowed_actions", [])
            action_lower = self.config.action.lower().strip()
            matched = any(a.lower().strip() == action_lower for a in allowed)

            if not matched:
                logger.info("Action denied: %r not in %r", self.config.action, allowed)
                chain.record("result_produced", {"denied": True}, "Action denied by policy")
                report = chain.finalize()
                return SecretProxyResult(
                    success=False,
                    result_text=f"Action denied: '{self.config.action}' is not allowed by policy. Allowed: {allowed}",
                    action_validated=False,
                    secret_deleted=True,
                    verification=_report_to_dict(report),
                )

            # Build LLM client with egress logging
            client = self._build_client(egress_log)

            # Generate policy
            policy = generate_policy("recall", self.config.action, client)
            chain.record("policy_generated", {
                "task_type": "recall",
                "constraint_count": len(policy.constraints),
                "policy_hash": hash_policy(policy),
            }, "Policy generated for recall action")

            # Call LLM
            result_text = self._call_llm_with_client(client)
            chain.record("llm_call", {"model": client.model}, "LLM called for action simulation")

            # Enforce policy
            policy_report = enforce_all(policy, {"result": result_text})
            chain.record("policy_enforced", {
                "all_passed": policy_report.all_passed,
                "policy_hash": policy_report.policy_hash,
            }, "Policy enforced deterministically on LLM output")

            chain.record("result_produced", {
                "success": True,
                "policy_passed": policy_report.all_passed,
            }, "Result produced and validated")

            report = chain.finalize()

            return SecretProxyResult(
                success=True,
                result_text=result_text,
                action_validated=True,
                secret_deleted=True,
                policy_report={
                    "all_passed": policy_report.all_passed,
                    "results": [
                        {"field": r.field, "passed": r.passed, "violations": r.violations}
                        for r in policy_report.results
                    ],
                    "policy_hash": policy_report.policy_hash,
                },
                policy_constraints=[
                    {
                        "field": c.field,
                        "pattern": c.pattern,
                        "deny_patterns": c.deny_patterns,
                        "max_length": c.max_length,
                        "rationale": c.rationale,
                    }
                    for c in policy.constraints
                ],
                egress_log=egress_log.to_dict_list(),
                verification=_report_to_dict(report),
            )
        finally:
            self.config.secret_value = None
            chain.record("sensitive_data_cleared", {}, "Secret value deleted from session memory")
            logger.info("Secret value deleted from session memory")

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
            "You are simulating the execution of a cloud API action inside a Trusted Execution Environment. "
            "Given the credential and action description, return a realistic simulated result. "
            "The result should look like real API output (JSON, text, or structured data). "
            "Be concise but realistic."
        )
        user_prompt = (
            f"A credential is available inside the TEE (not shown for security).\n"
            f"Action to execute: {self.config.action}\n\n"
            "Simulate executing this action and return the result."
        )

        response = client.create_message(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return client.extract_text(response)


def _report_to_dict(report: Any) -> dict:
    return {
        "session_id": report.session_id,
        "events": report.events,
        "chain_hashes": report.chain_hashes,
        "final_hash": report.final_hash,
        "attestation_claims": report.attestation_claims,
    }
