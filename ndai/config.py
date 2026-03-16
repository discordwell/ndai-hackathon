"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Database
    database_url: str = "postgresql+asyncpg://ndai:ndai@localhost:5432/ndai"
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60
    algorithm: str = "HS256"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"

    # TEE
    tee_mode: str = "simulated"  # "simulated" or "nitro"
    enclave_cpu_count: int = 2
    enclave_memory_mib: int = 1600
    enclave_eif_path: str = "ndai_enclave.eif"
    enclave_vsock_port: int = 5000

    # Security parameters (paper defaults)
    shamir_k: int = 3
    shamir_n: int = 5
    breach_detection_prob: float = 0.005
    breach_penalty: float = 7_500_000_000

    # Negotiation
    max_negotiation_rounds: int = 5
    negotiation_timeout_sec: int = 300


settings = Settings()
