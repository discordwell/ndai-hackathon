"""add known targets, verification proposals, and badge fields

Revision ID: j0e1f2a3b4c5
Revises: i9d0e1f2a3b4
Create Date: 2026-03-22 22:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "j0e1f2a3b4c5"
down_revision: Union[str, None] = "i9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── known_targets ──
    op.create_table(
        "known_targets",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(50), unique=True, nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("current_version", sa.String(100), nullable=False),
        sa.Column("verification_method", sa.String(30), nullable=False),
        sa.Column("base_image", sa.String(200)),
        sa.Column("packages_json", postgresql.JSON),
        sa.Column("services_json", postgresql.JSON),
        sa.Column("build_steps_json", postgresql.JSON),
        sa.Column("config_files_json", postgresql.JSON),
        sa.Column("service_user", sa.String(50), server_default="www-data"),
        sa.Column("poc_script_type", sa.String(20), nullable=False),
        sa.Column("poc_instructions", sa.Text(), nullable=False),
        sa.Column("escrow_amount_usd", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("icon_emoji", sa.String(10), server_default=""),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("version_feed_url", sa.String(500)),
        sa.Column("last_version_check", sa.DateTime(timezone=True)),
        sa.Column("platform_config_json", postgresql.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── target_builds ──
    op.create_table(
        "target_builds",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("known_targets.id"), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("build_type", sa.String(20), nullable=False),
        sa.Column("cache_key", sa.String(64), nullable=False),
        sa.Column("artifact_path", sa.String(500), nullable=False),
        sa.Column("pcr0", sa.String(200)),
        sa.Column("pcr1", sa.String(200)),
        sa.Column("pcr2", sa.String(200)),
        sa.Column("docker_image_hash", sa.String(200)),
        sa.Column("status", sa.String(20), server_default="building"),
        sa.Column("built_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_target_builds_target_id", "target_builds", ["target_id"])

    # ── verification_proposals ──
    op.create_table(
        "verification_proposals",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_pubkey", sa.String(64), nullable=False),
        sa.Column("target_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("known_targets.id"), nullable=False),
        sa.Column("target_version", sa.String(100), nullable=False),
        sa.Column("poc_script", sa.Text(), nullable=False),
        sa.Column("poc_script_type", sa.String(20), nullable=False),
        sa.Column("claimed_capability", sa.String(20), nullable=False),
        sa.Column("reliability_runs", sa.Integer(), server_default="3"),
        sa.Column("asking_price_eth", sa.Float(), nullable=False),
        sa.Column("deposit_required", sa.Boolean(), server_default="true"),
        sa.Column("deposit_amount_wei", sa.String(78)),
        sa.Column("deposit_tx_hash", sa.String(66)),
        sa.Column("deposit_proposal_id", sa.String(66)),
        sa.Column("status", sa.String(30), server_default="pending_deposit"),
        sa.Column("verification_result_json", postgresql.JSON),
        sa.Column("verification_chain_hash", sa.String(64)),
        sa.Column("attestation_pcr0", sa.String(200)),
        sa.Column("created_vuln_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("error_details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_verification_proposals_seller_pubkey", "verification_proposals", ["seller_pubkey"])
    op.create_index("ix_verification_proposals_target_id", "verification_proposals", ["target_id"])

    # ── Badge fields on vuln_identities ──
    op.add_column("vuln_identities", sa.Column("has_badge", sa.Boolean(), server_default="false"))
    op.add_column("vuln_identities", sa.Column("badge_type", sa.String(20)))
    op.add_column("vuln_identities", sa.Column("badge_tx_hash", sa.String(66)))
    op.add_column("vuln_identities", sa.Column("badge_awarded_at", sa.DateTime(timezone=True)))

    # ── Seed initial targets ──
    known_targets = sa.table(
        "known_targets",
        sa.column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String),
        sa.column("display_name", sa.String),
        sa.column("platform", sa.String),
        sa.column("current_version", sa.String),
        sa.column("verification_method", sa.String),
        sa.column("base_image", sa.String),
        sa.column("packages_json", postgresql.JSON),
        sa.column("services_json", postgresql.JSON),
        sa.column("build_steps_json", postgresql.JSON),
        sa.column("config_files_json", postgresql.JSON),
        sa.column("service_user", sa.String),
        sa.column("poc_script_type", sa.String),
        sa.column("poc_instructions", sa.Text),
        sa.column("escrow_amount_usd", sa.Integer),
        sa.column("icon_emoji", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("version_feed_url", sa.String),
        sa.column("platform_config_json", postgresql.JSON),
    )

    import uuid
    op.bulk_insert(known_targets, [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "chrome-linux")),
            "slug": "chrome-linux",
            "display_name": "Google Chrome (Linux)",
            "platform": "linux",
            "current_version": "124.0.6367.91",
            "verification_method": "nitro",
            "base_image": "ubuntu:22.04",
            "packages_json": [{"name": "chromium-browser", "version": "124.0.6367.91-0ubuntu0.22.04.1"}],
            "services_json": [{"name": "chromium", "start_command": "chromium-browser --headless --no-sandbox --disable-gpu --remote-debugging-port=9222", "health_check": "curl -sf http://localhost:9222/json/version > /dev/null", "timeout_sec": 30}],
            "build_steps_json": ["apt-get update && apt-get install -y curl chromium-browser"],
            "config_files_json": None,
            "service_user": "chrome",
            "poc_script_type": "html",
            "poc_instructions": """## Chrome PoC Instructions

Your PoC should be an **HTML file** that exploits a vulnerability in the Chromium renderer or sandbox.

### Environment
- Chromium runs in **headless mode** with `--no-sandbox` disabled (sandbox IS active)
- Remote debugging port 9222 is available for health checks only
- PoC is served on `http://localhost:8080/poc.html` and the browser navigates to it

### What to demonstrate
- **ACE**: Write a canary file to `/tmp/canary_ace` from outside the sandbox
- **Sandbox escape**: Read `/tmp/canary_lpe` (root-owned) from the renderer
- **Info leak**: Read `/tmp/canary_info` from process memory
- **Crash**: Trigger a renderer or browser crash (SIGSEGV/SIGABRT)

### Canary system
The platform plants random canary strings in the filesystem. Your exploit must read or write these canaries to prove capability. You do NOT define success — the oracle does.""",
            "escrow_amount_usd": 100,
            "icon_emoji": "\U0001f310",
            "is_active": True,
            "version_feed_url": "https://chromiumdash.appspot.com/fetch/milestones",
            "platform_config_json": None,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "firefox-linux")),
            "slug": "firefox-linux",
            "display_name": "Mozilla Firefox (Linux)",
            "platform": "linux",
            "current_version": "126.0",
            "verification_method": "nitro",
            "base_image": "ubuntu:22.04",
            "packages_json": [{"name": "firefox", "version": "126.0+build1-0ubuntu0.22.04.1"}],
            "services_json": [{"name": "firefox", "start_command": "firefox --headless --remote-debugging-port=9222", "health_check": "curl -sf http://localhost:9222/json/version > /dev/null", "timeout_sec": 30}],
            "build_steps_json": ["apt-get update && apt-get install -y curl firefox"],
            "config_files_json": None,
            "service_user": "firefox",
            "poc_script_type": "html",
            "poc_instructions": """## Firefox PoC Instructions

Your PoC should be an **HTML file** that exploits a vulnerability in Firefox.

### Environment
- Firefox runs in **headless mode**
- PoC is served on `http://localhost:8080/poc.html`

### Capability oracles
Same canary system as Chrome. The platform plants random strings; your exploit must retrieve them.""",
            "escrow_amount_usd": 100,
            "icon_emoji": "\U0001f525",
            "is_active": True,
            "version_feed_url": "https://product-details.mozilla.org/1.0/firefox_versions.json",
            "platform_config_json": None,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "ubuntu-lts")),
            "slug": "ubuntu-lts",
            "display_name": "Ubuntu Server LTS",
            "platform": "linux",
            "current_version": "24.04",
            "verification_method": "nitro",
            "base_image": "ubuntu:24.04",
            "packages_json": [
                {"name": "openssh-server", "version": "1:9.6p1-3ubuntu13"},
                {"name": "apache2", "version": "2.4.58-1ubuntu8"},
                {"name": "sudo", "version": "1.9.15p5-3ubuntu5"},
            ],
            "services_json": [
                {"name": "sshd", "start_command": "service ssh start", "health_check": "service ssh status", "timeout_sec": 10},
                {"name": "apache2", "start_command": "service apache2 start", "health_check": "curl -sf http://localhost/ > /dev/null", "timeout_sec": 10},
            ],
            "build_steps_json": None,
            "config_files_json": None,
            "service_user": "www-data",
            "poc_script_type": "bash",
            "poc_instructions": """## Ubuntu LTS PoC Instructions

Your PoC should be a **bash script** that exploits a vulnerability in Ubuntu server packages.

### Environment
- Ubuntu 24.04 LTS with standard server packages (OpenSSH, Apache2, sudo)
- Services are running with default configurations
- PoC runs as unprivileged user `poc`

### Capability oracles
- **LPE**: Read `/root/canary_lpe` (proves root escalation)
- **ACE**: Write to `/tmp/canary_ace` (proves code execution as service user)
- **Info leak**: Read `/proc/1/environ` or similar privileged data""",
            "escrow_amount_usd": 100,
            "icon_emoji": "\U0001f427",
            "is_active": True,
            "version_feed_url": "https://api.launchpad.net/devel/ubuntu/+archive/primary",
            "platform_config_json": None,
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "windows-server")),
            "slug": "windows-server",
            "display_name": "Windows Server 2022",
            "platform": "windows",
            "current_version": "10.0.20348",
            "verification_method": "ec2_windows",
            "base_image": None,
            "packages_json": None,
            "services_json": None,
            "build_steps_json": None,
            "config_files_json": None,
            "service_user": "SYSTEM",
            "poc_script_type": "powershell",
            "poc_instructions": """## Windows Server PoC Instructions

Your PoC should be a **PowerShell script** that exploits a vulnerability in Windows Server 2022.

### Environment
- Fresh Windows Server 2022 EC2 instance (m5.large)
- Standard Windows services running (IIS, RDP, WinRM)
- PoC executes via SSM Run Command as a limited user

### Capability oracles
- **LPE**: Read `C:\\canary\\canary_lpe.txt` (SYSTEM-only ACL)
- **ACE**: Write to `C:\\canary\\canary_ace.txt`
- **Info leak**: Read `C:\\canary\\canary_info.txt` from service process memory

### Trust model note
Windows verification runs in an EC2 VM, NOT a Nitro Enclave. The trust model is weaker than Linux targets.""",
            "escrow_amount_usd": 100,
            "icon_emoji": "\U0001fa9f",
            "is_active": True,
            "version_feed_url": None,
            "platform_config_json": {"ami_id": "", "instance_type": "m5.large"},
        },
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "ios-latest")),
            "slug": "ios-latest",
            "display_name": "Apple iOS (Latest)",
            "platform": "ios",
            "current_version": "18.4",
            "verification_method": "manual",
            "base_image": None,
            "packages_json": None,
            "services_json": None,
            "build_steps_json": None,
            "config_files_json": None,
            "service_user": "mobile",
            "poc_script_type": "manual",
            "poc_instructions": """## iOS PoC Instructions

iOS verification is currently **manual**. Submit your proposal and a platform operator will provision a Corellium virtual device for verification.

### What to provide
- Detailed exploit description
- IPA file or URL-based trigger
- Expected capability (sandbox escape, kernel exploit, etc.)

### Higher escrow
iOS verification requires a **$500 escrow** due to Corellium device costs. This is refunded if your exploit is verified.

### Timeline
Manual verification typically takes 24-72 hours after escrow confirmation.""",
            "escrow_amount_usd": 500,
            "icon_emoji": "\U0001f34e",
            "is_active": True,
            "version_feed_url": None,
            "platform_config_json": {"corellium_device_type": "iphone-15", "ios_version": "18.4"},
        },
    ])


def downgrade() -> None:
    op.drop_column("vuln_identities", "badge_awarded_at")
    op.drop_column("vuln_identities", "badge_tx_hash")
    op.drop_column("vuln_identities", "badge_type")
    op.drop_column("vuln_identities", "has_badge")
    op.drop_index("ix_verification_proposals_target_id", "verification_proposals")
    op.drop_index("ix_verification_proposals_seller_pubkey", "verification_proposals")
    op.drop_table("verification_proposals")
    op.drop_index("ix_target_builds_target_id", "target_builds")
    op.drop_table("target_builds")
    op.drop_table("known_targets")
