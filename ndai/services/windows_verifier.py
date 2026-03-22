"""Windows EC2 VM verification backend.

Launches a fresh Windows Server 2022 instance, installs target software
via SSM Run Command, plants canaries, runs PoC, checks results, terminates.

This runs OUTSIDE a Nitro Enclave — the trust model is weaker than Linux targets.
"""

import asyncio
import logging
import secrets
from typing import Any

from ndai.models.known_target import KnownTarget
from ndai.models.verification_proposal import VerificationProposal
from ndai.services.verification_dispatcher import VerificationOutcome

logger = logging.getLogger(__name__)


class WindowsVerifier:
    """Verification backend for Windows targets via EC2 + SSM."""

    async def verify(
        self,
        proposal: VerificationProposal,
        target: KnownTarget,
        progress_callback: Any = None,
    ) -> VerificationOutcome:
        """Run Windows verification via EC2 VM.

        Flow:
        1. Launch fresh Windows Server 2022 AMI
        2. Wait for SSM agent ready
        3. Plant canary files via PowerShell
        4. Transfer + execute PoC via SSM RunPowerShellScript
        5. Check canaries
        6. Terminate instance
        """
        from ndai.config import settings

        if not settings.windows_ami_id:
            return VerificationOutcome(
                success=False,
                status="error",
                error="Windows AMI not configured. Set WINDOWS_AMI_ID.",
            )

        instance_id = None
        try:
            import boto3

            if progress_callback:
                await progress_callback("building", {"message": "Launching Windows EC2 instance..."})

            ec2 = boto3.client("ec2")
            ssm = boto3.client("ssm")

            # Launch instance
            response = ec2.run_instances(
                ImageId=settings.windows_ami_id,
                InstanceType=settings.windows_instance_type,
                MinCount=1,
                MaxCount=1,
                SubnetId=settings.windows_subnet_id or None,
                SecurityGroupIds=[settings.windows_security_group_id] if settings.windows_security_group_id else [],
                IamInstanceProfile={"Name": "ndai-ssm-role"},
                TagSpecifications=[{
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": f"ndai-verify-{proposal.id}"},
                        {"Key": "ndai-proposal", "Value": str(proposal.id)},
                    ],
                }],
            )
            instance_id = response["Instances"][0]["InstanceId"]
            logger.info("Launched Windows instance %s for proposal %s", instance_id, proposal.id)

            if progress_callback:
                await progress_callback("building", {
                    "message": f"Waiting for instance {instance_id} to be ready...",
                })

            # Wait for instance running + SSM online
            waiter = ec2.get_waiter("instance_running")
            await asyncio.to_thread(waiter.wait, InstanceIds=[instance_id])

            # Wait for SSM agent
            for _ in range(30):
                await asyncio.sleep(10)
                try:
                    info = ssm.describe_instance_information(
                        Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
                    )
                    if info.get("InstanceInformationList"):
                        break
                except Exception:
                    pass
            else:
                return VerificationOutcome(
                    success=False, status="error",
                    error="SSM agent did not come online within 5 minutes",
                )

            if progress_callback:
                await progress_callback("verifying", {"message": "Planting canaries and running PoC..."})

            # Plant canaries
            ace_canary = secrets.token_hex(16)
            lpe_canary = secrets.token_hex(16)
            canary_script = f"""
New-Item -ItemType Directory -Force -Path C:\\canary
Set-Content -Path C:\\canary\\canary_lpe.txt -Value '{lpe_canary}'
$acl = Get-Acl C:\\canary\\canary_lpe.txt
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule("SYSTEM","FullControl","Allow")
$acl.AddAccessRule($rule)
Set-Acl C:\\canary\\canary_lpe.txt $acl
New-Item -ItemType File -Force -Path C:\\canary\\canary_ace.txt
"""
            await self._run_ssm_command(ssm, instance_id, canary_script)

            # Run PoC
            poc_result = await self._run_ssm_command(
                ssm, instance_id, proposal.poc_script,
                timeout_sec=min(settings.windows_ssm_timeout_sec, 900),
            )

            # Check canaries
            check_script = f"""
$aceContent = Get-Content -Path C:\\canary\\canary_ace.txt -ErrorAction SilentlyContinue
Write-Output "ACE_CANARY=$aceContent"
"""
            check_result = await self._run_ssm_command(ssm, instance_id, check_script)

            # Parse results
            # ACE: PoC must have written content to the initially-empty canary_ace.txt
            ace_found = False
            if "ACE_CANARY=" in check_result:
                ace_value = check_result.split("ACE_CANARY=")[1].split("\n")[0].strip()
                ace_found = len(ace_value) > 0

            # LPE: PoC must have read the SYSTEM-only canary and echoed it in its output.
            # The PoC stdout is captured in poc_result. If the lpe_canary value appears
            # in the PoC output, the exploit successfully escalated to read the file.
            lpe_found = lpe_canary in poc_result

            success = ace_found or lpe_found
            verified_level = "lpe" if lpe_found else ("ace" if ace_found else None)

            if progress_callback:
                phase = "passed" if success else "failed"
                await progress_callback(phase, {
                    "message": f"Windows verification {'passed' if success else 'failed'}",
                    "verified_level": verified_level,
                })

            return VerificationOutcome(
                success=success,
                capability_result={
                    "claimed": proposal.claimed_capability,
                    "verified_level": verified_level,
                    "ace_canary_found": ace_found,
                    "lpe_canary_found": lpe_found,
                    "platform": "windows",
                    "trust_note": "Verified in EC2 VM (no enclave attestation)",
                },
                status="passed" if success else "failed",
            )

        except ImportError:
            return VerificationOutcome(
                success=False, status="error",
                error="boto3 not installed. Install with: pip install boto3",
            )
        except Exception as e:
            logger.exception("Windows verification failed for proposal %s", proposal.id)
            return VerificationOutcome(success=False, status="error", error=str(e))
        finally:
            # Terminate instance
            if instance_id:
                try:
                    import boto3
                    ec2 = boto3.client("ec2")
                    ec2.terminate_instances(InstanceIds=[instance_id])
                    logger.info("Terminated Windows instance %s", instance_id)
                except Exception as e:
                    logger.error("Failed to terminate instance %s: %s", instance_id, e)

    async def _run_ssm_command(
        self,
        ssm: Any,
        instance_id: str,
        script: str,
        timeout_sec: int = 300,
    ) -> str:
        """Run a PowerShell script on the instance via SSM."""
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunPowerShellScript",
            Parameters={"commands": [script]},
            TimeoutSeconds=timeout_sec,
        )
        command_id = response["Command"]["CommandId"]

        # Poll for completion
        for _ in range(timeout_sec // 5):
            await asyncio.sleep(5)
            result = ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=instance_id,
            )
            if result["Status"] in ("Success", "Failed", "TimedOut", "Cancelled"):
                return result.get("StandardOutputContent", "")

        return ""
