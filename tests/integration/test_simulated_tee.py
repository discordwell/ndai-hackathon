"""Integration tests for SimulatedTEEProvider."""

import asyncio
import json

import pytest

from ndai.tee.provider import EnclaveConfig, EnclaveNotFoundError
from ndai.tee.simulated_provider import SimulatedTEEProvider


@pytest.fixture
def provider():
    return SimulatedTEEProvider()


@pytest.fixture
def config():
    return EnclaveConfig(eif_path="test.eif", vsock_port=5000)


class TestSimulatedTEELifecycle:
    async def test_launch_and_terminate(self, provider, config):
        identity = await provider.launch_enclave(config)
        assert identity.enclave_id.startswith("sim-")
        assert identity.enclave_cid >= 4
        await provider.terminate_enclave(identity.enclave_id)

    async def test_terminate_nonexistent(self, provider):
        # Should not raise
        await provider.terminate_enclave("nonexistent")

    async def test_send_receive(self, provider, config):
        identity = await provider.launch_enclave(config)
        inbox, outbox = provider.get_enclave_queues(identity.enclave_id)

        # Simulate enclave echoing a message
        test_msg = {"type": "test", "data": 42}
        await provider.send_message(identity.enclave_id, test_msg)

        # Read from inbox (what the enclave would receive)
        received = await asyncio.wait_for(inbox.get(), timeout=1.0)
        assert received == test_msg

        # Simulate enclave responding
        response_msg = {"type": "response", "result": "ok"}
        await outbox.put(response_msg)

        # Parent reads the response
        response = await asyncio.wait_for(
            provider.receive_message(identity.enclave_id), timeout=1.0
        )
        assert response == response_msg

        await provider.terminate_enclave(identity.enclave_id)

    async def test_attestation(self, provider, config):
        identity = await provider.launch_enclave(config)
        nonce = b"test-nonce-12345"

        doc_bytes = await provider.get_attestation(identity.enclave_id, nonce=nonce)
        doc = json.loads(doc_bytes)

        assert doc["type"] == "simulated_attestation"
        assert doc["enclave_id"] == identity.enclave_id
        assert doc["nonce"] == nonce.hex()
        assert "SIMULATED" in doc["warning"]
        assert doc["pcr0"] != ""

        await provider.terminate_enclave(identity.enclave_id)

    async def test_send_to_destroyed_enclave(self, provider, config):
        identity = await provider.launch_enclave(config)
        await provider.terminate_enclave(identity.enclave_id)

        with pytest.raises(EnclaveNotFoundError):
            await provider.send_message(identity.enclave_id, {"test": True})

    async def test_multiple_enclaves(self, provider, config):
        id1 = await provider.launch_enclave(config)
        id2 = await provider.launch_enclave(config)

        assert id1.enclave_id != id2.enclave_id
        assert id1.enclave_cid != id2.enclave_cid

        await provider.terminate_enclave(id1.enclave_id)
        await provider.terminate_enclave(id2.enclave_id)

    async def test_deterministic_pcrs(self, provider):
        config1 = EnclaveConfig(eif_path="same.eif")
        config2 = EnclaveConfig(eif_path="same.eif")
        config3 = EnclaveConfig(eif_path="different.eif")

        id1 = await provider.launch_enclave(config1)
        id2 = await provider.launch_enclave(config2)
        id3 = await provider.launch_enclave(config3)

        assert id1.pcr0 == id2.pcr0  # Same image -> same PCRs
        assert id1.pcr0 != id3.pcr0  # Different image -> different PCRs

        await provider.terminate_enclave(id1.enclave_id)
        await provider.terminate_enclave(id2.enclave_id)
        await provider.terminate_enclave(id3.enclave_id)
