"""add Apache httpd known target

Revision ID: l2a3b4c5d6e7
Revises: k1f2a3b4c5d6
Create Date: 2026-03-22 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "l2a3b4c5d6e7"
down_revision: Union[str, None] = "k1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    import uuid

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

    op.bulk_insert(known_targets, [
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "apache-httpd")),
            "slug": "apache-httpd",
            "display_name": "Apache HTTP Server",
            "platform": "linux",
            "current_version": "2.4.52-1ubuntu4.3",
            "verification_method": "nitro",
            "base_image": "ubuntu:22.04",
            "packages_json": [
                {"name": "apache2", "version": "2.4.52-1ubuntu4.3"},
                {"name": "apache2-utils", "version": "2.4.52-1ubuntu4.3"},
                {"name": "curl", "version": "7.81.0-1ubuntu1.13"},
            ],
            "services_json": [
                {
                    "name": "apache2",
                    "start_command": "service apache2 start",
                    "health_check": "curl -sf http://localhost/ > /dev/null",
                    "timeout_sec": 15,
                },
            ],
            "build_steps_json": None,
            "config_files_json": None,
            "service_user": "www-data",
            "poc_script_type": "bash",
            "poc_instructions": """## Apache httpd 2.4.52 PoC Instructions

Your PoC should be a **bash script** that exploits a vulnerability in Apache httpd 2.4.52.

### Environment
- Apache httpd runs as `www-data` on port 80
- Ubuntu 22.04 base image with default Apache config
- PoC runs as an unprivileged user with resource limits (60s CPU, 512MB RAM)

### Canary Oracle System
The enclave plants random canary strings. Your exploit must read or output these to prove capability. **You do not define success — the oracle does.**

| Capability | Canary Location | Permissions | How to Prove |
|-----------|----------------|-------------|--------------|
| **ACE** | `/var/lib/ndai-oracle/ace_canary` | 0644 (world-readable) | Output the file contents to stdout |
| **LPE** | `/var/lib/ndai-oracle/lpe_canary` | 0600 (root-only) | Escalate privileges, then read and output |
| **Crash** | N/A | N/A | Trigger SIGSEGV or SIGABRT in httpd |
| **DoS** | N/A | N/A | Make the service fail its health check |

### Example (ACE)
```bash
#!/bin/bash
# Your exploit goes here — this is just the canary read
cat /var/lib/ndai-oracle/ace_canary
```

The canary value is a random 32-character hex string generated fresh for each verification run. It cannot be predicted or hardcoded.""",
            "escrow_amount_usd": 100,
            "icon_emoji": "\U0001f527",
            "is_active": True,
            "version_feed_url": None,
            "platform_config_json": None,
        },
    ])


def downgrade() -> None:
    import uuid
    op.execute(
        sa.text("DELETE FROM known_targets WHERE id = :id"),
        {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "apache-httpd"))},
    )
