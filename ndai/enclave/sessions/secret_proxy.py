"""TEE session for Conditional Recall credential proxy."""

import logging
from dataclasses import dataclass

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


class SecretProxySession:
    def __init__(self, config: SecretProxyConfig):
        self.config = config

    def run(self) -> SecretProxyResult:
        try:
            allowed = self.config.policy.get("allowed_actions", [])
            action_lower = self.config.action.lower().strip()
            matched = any(a.lower().strip() == action_lower for a in allowed)

            if not matched:
                logger.info("Action denied: %r not in %r", self.config.action, allowed)
                return SecretProxyResult(
                    success=False,
                    result_text=f"Action denied: '{self.config.action}' is not allowed by policy. Allowed: {allowed}",
                    action_validated=False,
                    secret_deleted=True,
                )

            result_text = self._call_llm()

            return SecretProxyResult(
                success=True,
                result_text=result_text,
                action_validated=True,
                secret_deleted=True,
            )
        finally:
            self.config.secret_value = None
            logger.info("Secret value deleted from session memory")

    def _call_llm(self) -> str:
        """Call LLM to simulate executing the credentialed action.

        Uses create_message() + extract_text() — the actual LLM client interface.
        """
        from ndai.enclave.agents.llm_client import LLMClient
        from ndai.enclave.agents.openai_llm_client import OpenAILLMClient

        if self.config.llm_provider == "openai":
            client = OpenAILLMClient(api_key=self.config.api_key, model=self.config.llm_model)
        else:
            client = LLMClient(api_key=self.config.api_key, model=self.config.llm_model)

        system_prompt = (
            "You are simulating the execution of a cloud API action inside a Trusted Execution Environment. "
            "Given the credential and action description, return a realistic simulated result. "
            "The result should look like real API output (JSON, text, or structured data). "
            "Be concise but realistic."
        )
        user_prompt = (
            f"Credential (type/prefix): {self.config.secret_value[:8]}...\n"
            f"Action to execute: {self.config.action}\n\n"
            "Simulate executing this action and return the result."
        )

        response = client.create_message(
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return client.extract_text(response)
