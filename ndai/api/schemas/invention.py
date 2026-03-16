"""Invention request/response schemas."""

from pydantic import BaseModel


class InventionCreateRequest(BaseModel):
    title: str
    anonymized_summary: str | None = None
    category: str | None = None
    full_description: str
    technical_domain: str
    novelty_claims: list[str]
    prior_art_known: list[str] = []
    potential_applications: list[str] = []
    development_stage: str
    self_assessed_value: float
    outside_option_value: float
    confidential_sections: list[str] = []
    max_disclosure_fraction: float = 1.0


class InventionResponse(BaseModel):
    id: str
    title: str
    anonymized_summary: str | None
    category: str | None
    status: str


class ListingResponse(BaseModel):
    """Buyer-facing anonymized listing."""
    id: str
    title: str
    anonymized_summary: str | None
    category: str | None
    development_stage: str
