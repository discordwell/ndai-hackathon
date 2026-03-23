"""Agreement request/response schemas."""

from pydantic import BaseModel


class AgreementCreateRequest(BaseModel):
    invention_id: str
    budget_cap: float


class AgreementParamsRequest(BaseModel):
    alpha_0: float | None = None
    budget_cap: float | None = None


class AgreementResponse(BaseModel):
    id: str
    invention_id: str
    invention_title: str | None = None
    seller_id: str
    buyer_id: str
    status: str
    alpha_0: float | None
    budget_cap: float | None
    theta: float | None
    escrow_address: str | None = None
    escrow_tx_hash: str | None = None
    created_at: str | None = None


class NegotiationOutcomeResponse(BaseModel):
    outcome: str
    final_price: float | None
    reason: str | None = None
    negotiation_rounds: int | None = None
    omega_hat: float | None = None
    buyer_valuation: float | None = None
