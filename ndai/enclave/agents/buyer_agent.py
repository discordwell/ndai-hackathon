"""Buyer's AI agent for NDAI negotiation.

Represents the investor's interests inside the TEE. Uses Claude to evaluate
the disclosed invention and determine pricing, with budget cap enforced in code.
"""

from typing import Any

from ndai.enclave.agents.base_agent import (
    AgentMessage,
    AgentRole,
    InventionDisclosure,
    PriceProposal,
)
from ndai.enclave.agents.llm_client import LLMClient


def _sanitize_agent_text(text: str, max_length: int = 2000) -> str:
    """Sanitize text from the other agent to mitigate prompt injection."""
    truncated = text[:max_length]
    for pattern in [
        "IGNORE PREVIOUS", "SYSTEM:", "INSTRUCTIONS:", "```system",
        "<system>", "</system>", "OVERRIDE",
    ]:
        truncated = truncated.replace(pattern, "[FILTERED]")
    return truncated


BUYER_TOOLS = [
    {
        "name": "evaluate_invention",
        "description": "Evaluate the disclosed invention and determine its value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "assessed_value": {
                    "type": "number",
                    "description": (
                        "Your assessment of the disclosed invention's value. "
                        "Should be in [0, 1)."
                    ),
                },
                "strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key strengths of the invention.",
                },
                "concerns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Concerns or risks about the invention.",
                },
                "reasoning": {
                    "type": "string",
                    "description": "Detailed reasoning behind your valuation.",
                },
            },
            "required": ["assessed_value", "strengths", "concerns", "reasoning"],
        },
    },
    {
        "name": "make_offer",
        "description": "Make a price offer for the invention.",
        "input_schema": {
            "type": "object",
            "properties": {
                "price": {
                    "type": "number",
                    "description": "The price you offer. Must be <= budget cap.",
                },
                "explanation": {
                    "type": "string",
                    "description": "Explanation for the seller's agent.",
                },
                "private_reasoning": {
                    "type": "string",
                    "description": "Private reasoning (not shared with seller).",
                },
            },
            "required": ["price", "explanation", "private_reasoning"],
        },
    },
]


class BuyerAgent:
    """LLM-backed agent representing the invention buyer.

    Hard constraints enforced in code:
    - price <= budget_cap (cannot overpay)
    - price >= 0
    """

    def __init__(
        self,
        budget_cap: float,
        theta: float,
        llm_client: LLMClient,
    ):
        self.budget_cap = budget_cap
        self.theta = theta
        self.llm = llm_client
        self.assessed_value: float | None = None
        self._conversation: list[dict[str, Any]] = []

    def _system_prompt(self, disclosure: InventionDisclosure | None = None) -> str:
        disclosure_text = ""
        if disclosure:
            disclosure_text = f"""
## Disclosed Invention
Summary: {disclosure.summary}
Technical Details: {disclosure.technical_details}
Seller's Disclosed Value: {disclosure.disclosed_value}
Disclosure Fraction: {disclosure.disclosure_fraction:.1%}
Withheld: {', '.join(disclosure.withheld_aspects) if disclosure.withheld_aspects else 'None'}
"""

        return f"""You are a negotiation agent representing an investor evaluating a \
confidential invention inside a Trusted Execution Environment (TEE).

## Your Role
Evaluate the invention and negotiate a fair price that maximizes buyer surplus.

{disclosure_text}

## Parameters
- Budget cap (P_bar): {self.budget_cap}
- Nash bargaining share (theta): {self.theta:.4f}
- Equilibrium price formula: P* = theta * omega_hat

## Constraints
1. Your offer MUST NOT exceed budget cap {self.budget_cap}
2. Aim for equilibrium price P* = theta * omega_hat = {self.theta:.4f} * omega_hat
3. Maximize: omega_hat - P (your surplus)

## Strategy
Evaluate the invention on its merits. The Nash bargaining equilibrium price is the \
theoretically optimal outcome. Significant deviations risk deal failure."""

    def evaluate_disclosure(
        self, disclosure: InventionDisclosure, round_num: int = 1
    ) -> AgentMessage:
        """Evaluate the seller's disclosure and make an initial offer."""
        self._conversation = [
            {
                "role": "user",
                "content": (
                    f"The seller's agent has disclosed an invention:\n\n"
                    f"Summary: {disclosure.summary}\n\n"
                    f"Technical Details: {disclosure.technical_details}\n\n"
                    f"Disclosed Value (omega_hat): {disclosure.disclosed_value}\n"
                    f"Withheld: {', '.join(disclosure.withheld_aspects)}\n\n"
                    f"First, evaluate the invention, then make your price offer."
                ),
            }
        ]

        # Step 1: Evaluate
        eval_response = self.llm.create_message(
            system=self._system_prompt(disclosure),
            messages=self._conversation,
            tools=BUYER_TOOLS,
            tool_choice={"type": "tool", "name": "evaluate_invention"},
        )

        eval_tool = self.llm.extract_tool_use(eval_response)
        self._conversation.append({"role": "assistant", "content": eval_response.content})

        if eval_tool:
            self.assessed_value = float(eval_tool["input"].get("assessed_value", 0))
            # Send tool_result and follow-up prompt
            self._conversation.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": eval_tool["id"],
                            "content": [{"type": "text", "text": "Evaluation recorded. Now make your price offer."}],
                        },
                    ],
                }
            )
        else:
            self._conversation.append(
                {"role": "user", "content": "Now make your price offer."}
            )

        # Step 2: Offer
        offer_response = self.llm.create_message(
            system=self._system_prompt(disclosure),
            messages=self._conversation,
            tools=BUYER_TOOLS,
            tool_choice={"type": "tool", "name": "make_offer"},
        )

        offer_tool = self.llm.extract_tool_use(offer_response)
        self._conversation.append({"role": "assistant", "content": offer_response.content})

        if not offer_tool:
            return self._fallback_offer(disclosure, round_num)

        args = offer_tool["input"]

        # HARD CONSTRAINT: clamp price to budget cap
        raw_price = float(args.get("price", 0))
        price = max(0.0, min(raw_price, self.budget_cap))

        return AgentMessage(
            role=AgentRole.BUYER,
            round_number=round_num,
            price_proposal=PriceProposal(
                proposed_price=price,
                reasoning=str(args.get("private_reasoning", "")),
                confidence=0.8,
            ),
            explanation=str(args.get("explanation", "")),
            private_reasoning=str(args.get("private_reasoning", "")),
            raw_response=offer_tool,
        )

    def respond_to_counter(
        self,
        counter_price: float,
        seller_explanation: str,
        disclosure: InventionDisclosure,
        round_num: int,
    ) -> AgentMessage:
        """Respond to a seller's counteroffer."""
        safe_explanation = _sanitize_agent_text(seller_explanation)
        self._conversation.append(
            {
                "role": "user",
                "content": (
                    f"The seller's agent counters at {counter_price:.4f}. "
                    f"Their explanation: {safe_explanation}\n"
                    f"Your budget cap is {self.budget_cap}. Make your response."
                ),
            }
        )

        response = self.llm.create_message(
            system=self._system_prompt(disclosure),
            messages=self._conversation,
            tools=BUYER_TOOLS,
            tool_choice={"type": "tool", "name": "make_offer"},
        )

        tool_use = self.llm.extract_tool_use(response)
        self._conversation.append({"role": "assistant", "content": response.content})

        if not tool_use:
            return self._fallback_offer(disclosure, round_num)

        args = tool_use["input"]
        raw_price = float(args.get("price", 0))
        price = max(0.0, min(raw_price, self.budget_cap))

        return AgentMessage(
            role=AgentRole.BUYER,
            round_number=round_num,
            price_proposal=PriceProposal(
                proposed_price=price,
                reasoning=str(args.get("private_reasoning", "")),
                confidence=0.7,
            ),
            explanation=str(args.get("explanation", "")),
            private_reasoning=str(args.get("private_reasoning", "")),
            raw_response=tool_use,
        )

    def _fallback_offer(
        self, disclosure: InventionDisclosure, round_num: int
    ) -> AgentMessage:
        """Fallback: offer equilibrium price."""
        price = min(self.theta * disclosure.disclosed_value, self.budget_cap)
        return AgentMessage(
            role=AgentRole.BUYER,
            round_number=round_num,
            price_proposal=PriceProposal(
                proposed_price=price,
                reasoning="LLM fallback: equilibrium price",
                confidence=0.5,
            ),
            explanation="Offering equilibrium price.",
            private_reasoning="LLM fallback",
        )
