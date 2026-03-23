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


class InventionUpdateRequest(BaseModel):
    title: str | None = None
    anonymized_summary: str | None = None
    category: str | None = None
    full_description: str | None = None
    technical_domain: str | None = None
    novelty_claims: list[str] | None = None
    prior_art_known: list[str] | None = None
    potential_applications: list[str] | None = None
    development_stage: str | None = None
    self_assessed_value: float | None = None
    outside_option_value: float | None = None
    confidential_sections: list[str] | None = None
    max_disclosure_fraction: float | None = None


class InventionResponse(BaseModel):
    id: str
    title: str
    anonymized_summary: str | None
    category: str | None
    status: str
    full_description: str | None = None
    technical_domain: str | None = None
    development_stage: str | None = None
    self_assessed_value: float | None = None
    outside_option_value: float | None = None
    novelty_claims: list[str] | None = None
    prior_art_known: list[str] | None = None
    potential_applications: list[str] | None = None
    confidential_sections: list[str] | None = None
    max_disclosure_fraction: float | None = None
    created_at: str | None = None


class ListingResponse(BaseModel):
    """Buyer-facing anonymized listing."""
    id: str
    title: str
    anonymized_summary: str | None
    category: str | None
    development_stage: str
