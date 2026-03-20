"""Tests for session verification chain."""

from ndai.enclave.verification import (
    SessionVerificationChain,
    VerificationReport,
)


class TestSessionVerificationChain:
    def test_chain_builds(self):
        chain = SessionVerificationChain(session_id="test-session")
        chain.record("session_start", {"config": "test"}, "Session initialized")
        chain.record("llm_call", {"prompt": "hello"}, "Called LLM")
        chain.record("result_produced", {"result": "ok"}, "Got result")

        report = chain.finalize()
        assert report.session_id == "test-session"
        assert len(report.events) == 3
        assert len(report.chain_hashes) == 3
        assert len(report.final_hash) == 64

    def test_linked_hashes(self):
        chain = SessionVerificationChain()
        chain.record("a", "data1", "first")
        chain.record("b", "data2", "second")
        report = chain.finalize()
        # Each hash depends on the previous
        assert report.chain_hashes[0] != report.chain_hashes[1]

    def test_tamper_detection(self):
        """If we modify an event, the final hash must change."""
        chain1 = SessionVerificationChain(session_id="s1")
        chain1.record("session_start", {"x": 1}, "start")
        chain1.record("llm_call", {"prompt": "hello"}, "call")
        report1 = chain1.finalize()

        chain2 = SessionVerificationChain(session_id="s1")
        chain2.record("session_start", {"x": 1}, "start")
        chain2.record("llm_call", {"prompt": "TAMPERED"}, "call")
        report2 = chain2.finalize()

        assert report1.final_hash != report2.final_hash

    def test_claims_generation(self):
        chain = SessionVerificationChain()
        chain.record("session_start", {}, "start")
        chain.record("policy_generated", {}, "gen")
        chain.record("policy_enforced", {}, "enforce")
        chain.record("llm_call", {}, "call 1")
        chain.record("llm_call", {}, "call 2")
        chain.record("sensitive_data_cleared", {}, "cleared")

        report = chain.finalize()
        claims = report.attestation_claims
        assert any("deterministically" in c for c in claims)
        assert any("2 time(s)" in c for c in claims)
        assert any("deleted" in c.lower() for c in claims)

    def test_empty_chain(self):
        chain = SessionVerificationChain()
        report = chain.finalize()
        assert report.events == []
        assert report.chain_hashes == []
        assert report.attestation_claims == []
        # Final hash is genesis
        assert report.final_hash == "0" * 64

    def test_deterministic_for_same_data(self):
        """Same events in same order produce same chain hashes."""
        def build():
            c = SessionVerificationChain(session_id="det")
            c.record("a", {"k": "v"}, "desc")
            c.record("b", {"k": "v"}, "desc")
            return c.finalize()

        r1 = build()
        r2 = build()
        assert r1.chain_hashes == r2.chain_hashes
        assert r1.final_hash == r2.final_hash
