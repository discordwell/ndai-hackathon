import React, { useState, useEffect } from "react";
import { getAgreement, setAgreementParams, confirmAgreement, getEscrowState } from "../../api/agreements";
import { startNegotiation, getNegotiationStatus } from "../../api/negotiations";
import { Card } from "../../components/shared/Card";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { OutcomeDisplay } from "../../components/negotiation/OutcomeDisplay";
import { NegotiationProgress } from "../../components/negotiation/NegotiationProgress";
import { MechanismExplorer } from "../../components/negotiation/MechanismExplorer";
import { EscrowStepper } from "../../components/shared/EscrowStepper";
import { VerificationPanel } from "../../components/shared/VerificationPanel";
import { useNegotiationStream } from "../../hooks/useNegotiationStream";
import { useAuth } from "../../contexts/AuthContext";
import type { AgreementResponse, NegotiationStatusResponse, EscrowStateResponse } from "../../api/types";

export function BuyerAgreementDetailPage({ id }: { id: string }) {
  const { token } = useAuth();
  const [agreement, setAgreement_] = useState<AgreementResponse | null>(null);
  const [negStatus, setNegStatus] = useState<NegotiationStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState("");
  const [alpha0, setAlpha0] = useState("0.3");
  const [escrowData, setEscrowData] = useState<any>(null);

  const { phase, isComplete, connect: connectSSE } = useNegotiationStream(id, token || "");

  async function load() {
    try {
      const a = await getAgreement(id);
      setAgreement_(a);
      if (a.status.startsWith("completed_") || a.status === "confirmed") {
        try {
          const s = await getNegotiationStatus(id);
          setNegStatus(s);
        } catch {
          // no negotiation yet
        }
      }
      if (a.escrow_address) {
        try {
          const es = await getEscrowState(id);
          setEscrowData(es);
        } catch {
          // blockchain unavailable
        }
      }
    } catch {
      setError("Agreement not found");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  // Refresh when SSE signals completion
  useEffect(() => {
    if (isComplete) {
      load();
    }
  }, [isComplete]);

  async function handleSetParams() {
    setActionLoading(true);
    setError("");
    try {
      const updated = await setAgreementParams(id, { alpha_0: parseFloat(alpha0) });
      setAgreement_(updated);
    } catch (err: any) {
      setError(err.detail || "Failed to set params");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleConfirm() {
    setActionLoading(true);
    setError("");
    try {
      const updated = await confirmAgreement(id);
      setAgreement_(updated);
    } catch (err: any) {
      setError(err.detail || "Failed to confirm");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleStartNegotiation() {
    setActionLoading(true);
    setError("");
    try {
      const status = await startNegotiation(id);
      setNegStatus(status);
      // Connect SSE for real-time progress
      connectSSE();
      // Also poll as fallback
      if (status.status === "pending" || status.status === "running") {
        pollStatus();
      }
    } catch (err: any) {
      setError(err.detail || "Failed to start negotiation");
    } finally {
      setActionLoading(false);
    }
  }

  async function pollStatus() {
    let retries = 0;
    const maxRetries = 60;
    const poll = async () => {
      try {
        const s = await getNegotiationStatus(id);
        setNegStatus(s);
        retries = 0;
        if (s.status === "pending" || s.status === "running") {
          setTimeout(poll, 2000);
        } else {
          const a = await getAgreement(id);
          setAgreement_(a);
        }
      } catch {
        retries++;
        if (retries < maxRetries) {
          setTimeout(poll, 3000);
        } else {
          setError("Polling timed out. Refresh the page to check status.");
        }
      }
    };
    setTimeout(poll, 2000);
  }

  if (loading) return <LoadingSpinner />;
  if (!agreement) return <div className="text-red-600">{error || "Not found"}</div>;

  const isNegotiating = negStatus?.status === "pending" || negStatus?.status === "running";
  const isCompleted = agreement.status.startsWith("completed_");
  const canSetParams = agreement.status === "proposed";
  const canConfirm = agreement.status === "proposed" && agreement.theta !== null;
  const canNegotiate = agreement.status === "confirmed" && !isNegotiating;

  return (
    <div className="max-w-2xl">
      <a
        href="#/buyer/agreements"
        className="text-sm text-ndai-600 hover:text-ndai-700 mb-4 inline-block"
      >
        &larr; Back to agreements
      </a>
      <h1 className="text-2xl font-bold mb-6">Agreement Detail</h1>

      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-4">
          {error}
        </div>
      )}

      {agreement.escrow_address && escrowData && (
        <div className="mb-4">
          <EscrowStepper
            state={escrowData.state || "Funded"}
            creationTxHash={agreement.escrow_tx_hash || undefined}
          />
        </div>
      )}

      <Card className="mb-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Status</span>
            <div className="mt-1">
              <StatusBadge status={agreement.status} />
            </div>
          </div>
          <div>
            <span className="text-gray-500">Invention</span>
            <div className="mt-1 font-mono text-xs">
              {agreement.invention_id.slice(0, 12)}...
            </div>
          </div>
          <div>
            <span className="text-gray-500">Budget Cap</span>
            <div className="mt-1 font-medium">
              {agreement.budget_cap?.toFixed(2) ?? "\u2014"}
            </div>
          </div>
          <div>
            <span className="text-gray-500">Theta</span>
            <div className="mt-1 font-medium">
              {agreement.theta?.toFixed(3) ?? "\u2014"}
            </div>
          </div>
          <div>
            <span className="text-gray-500">Alpha-0</span>
            <div className="mt-1 font-medium">
              {agreement.alpha_0?.toFixed(2) ?? "\u2014"}
            </div>
          </div>
        </div>
      </Card>

      {canSetParams && (
        <Card className="mb-6">
          <h3 className="font-semibold mb-3">Set Negotiation Parameters</h3>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="block text-sm text-gray-500 mb-1">
                Outside Option (alpha_0)
              </label>
              <input
                type="number"
                min="0"
                max="1"
                step="0.05"
                value={alpha0}
                onChange={(e) => setAlpha0(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
              />
            </div>
            <button
              onClick={handleSetParams}
              disabled={actionLoading}
              className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 text-sm font-medium"
            >
              Set
            </button>
          </div>
        </Card>
      )}

      {canConfirm && (
        <Card className="mb-6">
          <h3 className="font-semibold mb-2">Confirm Delegation</h3>
          <p className="text-sm text-gray-500 mb-3">
            Confirm that you agree to delegate negotiation to AI agents inside
            the TEE with the parameters above.
          </p>
          <button
            onClick={handleConfirm}
            disabled={actionLoading}
            className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 text-sm font-medium"
          >
            Confirm Delegation
          </button>
        </Card>
      )}

      {canNegotiate && (
        <Card className="mb-6">
          <h3 className="font-semibold mb-2">Start Negotiation</h3>
          <p className="text-sm text-gray-500 mb-3">
            Launch the AI-powered negotiation inside the Trusted Execution
            Environment. This may take a minute.
          </p>
          <button
            onClick={handleStartNegotiation}
            disabled={actionLoading}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium"
          >
            {actionLoading ? "Starting..." : "Start Negotiation"}
          </button>
        </Card>
      )}

      {isNegotiating && (
        <Card className="mb-6">
          <div className="font-medium mb-2">Negotiation in progress...</div>
          <NegotiationProgress phase={phase} />
          <div className="text-sm text-gray-500 mt-2">
            AI agents are negotiating inside the TEE
          </div>
        </Card>
      )}

      {negStatus?.status === "completed" && negStatus.outcome && (
        <OutcomeDisplay outcome={negStatus.outcome} />
      )}

      {negStatus?.status === "error" && (
        <Card className="mb-6 border-red-200">
          <div className="text-red-700 font-medium">Negotiation Error</div>
          <div className="text-sm text-red-600 mt-1">
            {negStatus.error || "An error occurred during negotiation"}
          </div>
        </Card>
      )}

      <div className="mb-6">
        <MechanismExplorer
          initialBudgetCap={agreement.budget_cap ?? 0.8}
          initialAlpha0={agreement.alpha_0 ?? 0.3}
          initialOmegaHat={negStatus?.outcome?.omega_hat ?? 0.5}
          initialBuyerValue={negStatus?.outcome?.buyer_valuation ?? 0.5}
        />
      </div>

      {isCompleted && (
        <VerificationPanel verification={null} escrowData={escrowData} />
      )}
    </div>
  );
}
