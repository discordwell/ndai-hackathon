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

    # LLM Provider ("anthropic" or "openai")
    llm_provider: str = "anthropic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # TEE
    tee_mode: str = "simulated"  # "simulated", "nitro", or "dstack"
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

    # CDP / Browser
    browser_enabled: bool = False
    chrome_cdp_url: str = "ws://localhost:9222"
    cdp_vsock_port: int = 5003

    # Blockchain
    base_sepolia_rpc_url: str = ""
    escrow_factory_address: str = ""
    escrow_operator_key: str = ""
    escrow_operator_address: str = ""
    chain_id: int = 84532
    blockchain_enabled: bool = False

    # Poker
    poker_enabled: bool = True
    poker_action_timeout_sec: int = 30
    poker_table_factory_address: str = ""
    poker_max_tables: int = 10

    # Vulnerability marketplace
    vuln_marketplace_enabled: bool = True
    vuln_escrow_factory_address: str = ""
    platform_fee_address: str = ""

    # Frontend
    frontend_dir: str = ""  # Override FRONTEND_DIST path (for zdayzk.com deployment)

    # Privacy / Tor
    privacy_mode: bool = False
    onion_address: str = ""

    # Vulnerability verification (Phase 3)
    vuln_verify_enabled: bool = True
    vuln_eif_build_dir: str = "/tmp/ndai-eif-builds"
    vuln_eif_store_dir: str = "/opt/ndai/eifs"
    vuln_poc_timeout_sec: int = 120
    vuln_poc_max_memory_mb: int = 512
    vuln_overlay_max_size_mb: int = 500
    vuln_verify_enclave_memory_mib: int = 2048

    # Known Targets & Verification Proposals
    known_targets_enabled: bool = True
    verification_deposit_address: str = ""  # VerificationDeposit.sol contract address
    target_update_interval_hours: int = 6

    # Windows verification (EC2 VM path)
    windows_ami_id: str = ""  # Windows Server 2022 AMI
    windows_instance_type: str = "m5.large"
    windows_ssm_timeout_sec: int = 900  # 15 min max
    windows_subnet_id: str = ""
    windows_security_group_id: str = ""

    # iOS verification (Corellium)
    corellium_api_key: str = ""
    corellium_api_url: str = "https://app.corellium.com/api"


settings = Settings()
