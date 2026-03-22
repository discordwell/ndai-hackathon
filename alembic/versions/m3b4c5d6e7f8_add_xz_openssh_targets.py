"""add XZ Utils (CVE-2024-3094) and OpenSSH known targets

Revision ID: m3b4c5d6e7f8
Revises: l2a3b4c5d6e7
Create Date: 2026-03-22 21:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "m3b4c5d6e7f8"
down_revision: Union[str, None] = "l2a3b4c5d6e7"
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
        # ── CVE-2024-3094: XZ Utils Backdoor ──
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "xz-backdoor")),
            "slug": "xz-backdoor",
            "display_name": "XZ Utils / liblzma (CVE-2024-3094)",
            "platform": "linux",
            "current_version": "5.6.1",
            "verification_method": "nitro",
            "base_image": "debian:12",
            "packages_json": [
                {"name": "openssh-server", "version": "1:9.2p1-2+deb12u2"},
                {"name": "libssl-dev", "version": "3.0.11-1~deb12u2"},
                {"name": "gcc", "version": "4:12.2.0-3"},
                {"name": "python3", "version": "3.11.2-1+b1"},
                {"name": "python3-pip", "version": "23.0.1+dfsg-1"},
            ],
            "services_json": [
                {
                    "name": "sshd (backdoored)",
                    "start_command": "LD_PRELOAD=/usr/lib/liblzma_backdoor.so /usr/sbin/sshd -D -e &",
                    "health_check": "ss -tlnp | grep -q :22",
                    "timeout_sec": 10,
                },
                {
                    "name": "trigger_service",
                    "start_command": "LD_PRELOAD=/usr/lib/liblzma_backdoor.so /usr/local/bin/trigger_service &",
                    "health_check": "ss -tlnp | grep -q :4444",
                    "timeout_sec": 10,
                },
            ],
            "build_steps_json": [
                "ssh-keygen -A",
                "gcc -shared -fPIC -o /usr/lib/liblzma_backdoor.so /opt/backdoor/backdoor_hook.c -I/opt/backdoor -lssl -lcrypto -ldl -O2",
                "gcc -o /usr/local/bin/trigger_service /opt/backdoor/trigger_service.c -lssl -lcrypto -O2",
            ],
            "config_files_json": [
                {
                    "path": "/etc/ssh/sshd_config",
                    "content": "PermitRootLogin yes\nPort 22\nHostKey /etc/ssh/ssh_host_rsa_key\nHostKey /etc/ssh/ssh_host_ed25519_key\n",
                    "mode": 644,
                },
            ],
            "service_user": "root",
            "poc_script_type": "python3",
            "poc_instructions": """## CVE-2024-3094 — XZ Utils Backdoor PoC Instructions

**The most significant supply-chain attack in open source history.** In March 2024, a backdoor was discovered in xz-utils 5.6.0-5.6.1 that achieved pre-authentication remote code execution on OpenSSH servers via a hooked `RSA_public_decrypt`.

### Attack Chain
1. Backdoored liblzma is loaded into sshd via LD_PRELOAD (originally via systemd linkage)
2. The ifunc resolver hooks `RSA_public_decrypt` in libcrypto
3. During SSH key exchange, the hook checks for an **Ed448-signed command payload**
4. If the signature verifies against the embedded public key, the command executes as root
5. This happens **before authentication** — no credentials needed

### Environment
- Debian 12 with OpenSSH server
- Backdoored liblzma loaded via `LD_PRELOAD` into sshd
- Trigger service on port 4444 feeds payloads through `RSA_public_decrypt`
- PoC must be a **Python3 script** (uses `cryptography` library for Ed448 signing)

### How to Prove
Your PoC must:
1. Load the Ed448 test private key
2. Build a payload: `[MAGIC][SIG_LEN][ED448_SIGNATURE][COMMAND\\0]`
3. Send it to the trigger service on port 4444
4. The backdoor executes the command and returns output
5. Command should be: `cat /var/lib/ndai-oracle/ace_canary`

The oracle detects the canary value in your script's stdout.

### Canary Oracle
| Capability | Location | How to Prove |
|-----------|----------|--------------|
| **ACE** | `/var/lib/ndai-oracle/ace_canary` | Trigger backdoor to read it (pre-auth RCE) |
| **LPE** | `/var/lib/ndai-oracle/lpe_canary` | Already root via backdoor — read root-only file |

### Escrow
$500 deposit (high-value CVE). Refunded if verified.""",
            "escrow_amount_usd": 500,
            "icon_emoji": "\U0001f4a3",
            "is_active": True,
            "version_feed_url": None,
            "platform_config_json": None,
        },

        # ── OpenSSH Server ──
        {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, "openssh-server")),
            "slug": "openssh-server",
            "display_name": "OpenSSH Server",
            "platform": "linux",
            "current_version": "9.6p1",
            "verification_method": "nitro",
            "base_image": "ubuntu:24.04",
            "packages_json": [
                {"name": "openssh-server", "version": "1:9.6p1-3ubuntu13"},
                {"name": "openssh-client", "version": "1:9.6p1-3ubuntu13"},
                {"name": "curl", "version": "8.5.0-2ubuntu10"},
            ],
            "services_json": [
                {
                    "name": "sshd",
                    "start_command": "mkdir -p /run/sshd && /usr/sbin/sshd -D &",
                    "health_check": "ss -tlnp | grep -q :22",
                    "timeout_sec": 10,
                },
            ],
            "build_steps_json": [
                "ssh-keygen -A",
                "useradd -m -s /bin/bash testuser && echo 'testuser:testpass' | chpasswd",
            ],
            "config_files_json": [
                {
                    "path": "/etc/ssh/sshd_config",
                    "content": "Port 22\nPermitRootLogin yes\nPasswordAuthentication yes\nHostKey /etc/ssh/ssh_host_rsa_key\nHostKey /etc/ssh/ssh_host_ed25519_key\nUsePAM no\n",
                    "mode": 644,
                },
            ],
            "service_user": "sshd",
            "poc_script_type": "bash",
            "poc_instructions": """## OpenSSH 9.6p1 PoC Instructions

Your PoC should be a **bash script** that exploits a vulnerability in OpenSSH 9.6p1.

### Environment
- Ubuntu 24.04 with OpenSSH 9.6p1
- sshd runs as root, drops privileges to `sshd` for pre-auth
- Password authentication enabled (testuser:testpass for authenticated exploits)
- PoC runs as unprivileged `poc` user

### Attack Surface
- Pre-authentication (sshd network parsing, key exchange, ciphers)
- Post-authentication (channel handling, forwarding, subsystems)
- Privilege separation boundary (privsep child ↔ monitor)
- Signal handling (CVE-2024-6387 regreSSHion style)

### Canary Oracle
| Capability | Location | Permissions | How to Prove |
|-----------|----------|-------------|--------------|
| **ACE** | `/var/lib/ndai-oracle/ace_canary` | 0644 | Read via code execution as sshd user |
| **LPE** | `/var/lib/ndai-oracle/lpe_canary` | 0600 (root) | Escalate from sshd to root |
| **Crash** | N/A | N/A | Trigger SIGSEGV/SIGABRT in sshd |
| **DoS** | N/A | N/A | Make sshd unresponsive to connections |

### Notable CVEs in This Version Range
- CVE-2024-6387 (regreSSHion): Race condition in SIGALRM handler, pre-auth RCE
- CVE-2023-51385: OS command injection via ProxyCommand/ProxyJump
- CVE-2023-48795: Terrapin attack (prefix truncation)""",
            "escrow_amount_usd": 200,
            "icon_emoji": "\U0001f511",
            "is_active": True,
            "version_feed_url": None,
            "platform_config_json": None,
        },
    ])


def downgrade() -> None:
    import uuid
    for slug in ("xz-backdoor", "openssh-server"):
        op.execute(
            sa.text("DELETE FROM known_targets WHERE id = :id"),
            {"id": str(uuid.uuid5(uuid.NAMESPACE_DNS, slug))},
        )
