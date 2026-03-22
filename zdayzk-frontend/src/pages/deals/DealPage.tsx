import React, { useState, useEffect } from "react";
import { getVulnAgreement, startVulnNegotiation, getVulnOutcome } from "../../api/vulns";
import type { VulnAgreementResponse } from "../../api/types";
import { useNegotiationStream, type VulnOutcome } from "../../hooks/useNegotiationStream";
import { DealStatusTimeline } from "../../components/deals/DealStatusTimeline";
import { NegotiationLive } from "../../components/deals/NegotiationLive";
import { OutcomeCard } from "../../components/deals/OutcomeCard";
import { EscrowPanel } from "../../components/deals/EscrowPanel";
import { DeliveryPanel } from "../../components/deals/DeliveryPanel";

export function DealPage({ dealId }: { dealId: string }) {
  const [deal, setDeal] = useState<VulnAgreementResponse | null>(null);
  const [outcome, setOutcome] = useState<VulnOutcome | null>(null);
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const stream = useNegotiationStream(dealId);

  // Load deal + existing outcome
  useEffect(() => {
    Promise.all([
      getVulnAgreement(dealId),
      getVulnOutcome(dealId).catch(() => null),
    ]).then(([d, o]) => {
      setDeal(d);
      if (o) setOutcome(o);
      setLoading(false);
    }).catch((e) => {
      setError(e.detail || "Failed to load deal");
      setLoading(false);
    });
  }, [dealId]);

  // Use stream outcome when it arrives
  useEffect(() => {
    if (stream.outcome) {
      setOutcome(stream.outcome);
    }
  }, [stream.outcome]);

  async function handleStartNegotiation() {
    setStarting(true);
    setError("");
    try {
      await startVulnNegotiation(dealId);
      stream.connect();
    } catch (err: any) {
      setError(err.detail || "Failed to start negotiation");
    } finally {
      setStarting(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  if (!deal) {
    return (
      <div className="glass-card p-6 text-center">
        <p className="text-danger-400 text-sm">{error || "Deal not found"}</p>
      </div>
    );
  }

  const isDealAccepted = deal.status === "accepted" || deal.status === "completed";
  const canStartNegotiation = deal.status === "pending" || deal.status === "confirmed";

  return (
    <div className="animate-fade-in">
      <a href="#/deals" className="text-xs text-gray-500 hover:text-gray-300 transition-colors mb-4 inline-block">
        &larr; Back to Deals
      </a>

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-white">Deal</h1>
          <p className="text-xs font-mono text-gray-500 mt-1">{dealId}</p>
        </div>
        <span
          className={`text-xs px-3 py-1 rounded border font-medium ${
            deal.status === "completed"
              ? "bg-success-500/20 text-success-400 border-success-500/30"
              : deal.status === "running"
              ? "bg-accent-400/20 text-accent-400 border-accent-400/30"
              : "bg-surface-700 text-gray-400 border-surface-600"
          }`}
        >
          {deal.status}
        </span>
      </div>

      {error && (
        <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-3 rounded-lg mb-6">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Timeline + Controls */}
        <div className="space-y-6">
          {/* Deal Info */}
          <div className="glass-card p-5">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Deal Info</h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-gray-500">Vulnerability</span>
                <span className="font-mono text-gray-300">{deal.vulnerability_id.slice(0, 12)}...</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Budget Cap</span>
                <span className="font-mono text-accent-400">{deal.budget_cap?.toFixed(4) ?? "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Alpha-0</span>
                <span className="font-mono text-gray-300">{deal.alpha_0?.toFixed(2) ?? "—"}</span>
              </div>
            </div>
          </div>

          {/* Timeline */}
          {(stream.events.length > 0 || deal.status === "running") && (
            <div className="glass-card p-5">
              <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Progress</h3>
              <DealStatusTimeline events={stream.events} />
            </div>
          )}

          {/* Start button */}
          {canStartNegotiation && !stream.isConnected && (
            <button
              onClick={handleStartNegotiation}
              disabled={starting}
              className="w-full py-3 bg-accent-400 text-surface-950 font-semibold rounded-lg hover:bg-accent-300 disabled:opacity-50 transition-colors text-sm"
            >
              {starting ? "Starting..." : "Start Negotiation"}
            </button>
          )}
        </div>

        {/* Right: Negotiation + Outcome + Escrow */}
        <div className="lg:col-span-2 space-y-6">
          {/* Live negotiation */}
          {(stream.events.length > 0 || stream.isConnected) && (
            <NegotiationLive events={stream.events} isConnected={stream.isConnected} />
          )}

          {/* Outcome */}
          {outcome && <OutcomeCard outcome={outcome} />}

          {/* Escrow (show after outcome) */}
          {outcome && (outcome.outcome === "agreement" || outcome.outcome === "deal") && (
            <EscrowPanel
              escrowAddress={(deal as any).escrow_address}
              canAccept
              canReject
            />
          )}

          {/* Delivery */}
          {isDealAccepted && (
            <DeliveryPanel agreementId={dealId} isAccepted={isDealAccepted} />
          )}
        </div>
      </div>
    </div>
  );
}
