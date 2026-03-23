import React, { useState, useEffect } from "react";
import { getAgreement, getEscrowState } from "../../api/agreements";
import { getNegotiationOutcome } from "../../api/negotiations";
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
import type { AgreementResponse, NegotiationOutcomeResponse } from "../../api/types";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

const STATUS_STEPS = [
  { key: "proposed", label: "Proposed" },
  { key: "confirmed", label: "Confirmed" },
  { key: "completed", label: "Completed" },
];

export function SellerAgreementDetailPage({ id }: { id: string }) {
  const { token } = useAuth();
  const [agreement, setAgreement] = useState<AgreementResponse | null>(null);
  const [outcome, setOutcome] = useState<NegotiationOutcomeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [escrowData, setEscrowData] = useState<any>(null);
  const [auditLog, setAuditLog] = useState<any[]>([]);
  const [showAudit, setShowAudit] = useState(false);

  const { phase, isComplete, progressLog, connect: connectSSE } = useNegotiationStream(id, token || "");

  async function load() {
    try {
      const a = await getAgreement(id);
      setAgreement(a);
      if (a.status.startsWith("completed_")) {
        const o = await getNegotiationOutcome(id);
        setOutcome(o);
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
      // handled by null state
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  useEffect(() => {
    if (isComplete) load();
  }, [isComplete]);

  // Connect SSE if negotiation is in progress
  useEffect(() => {
    if (agreement && agreement.status === "confirmed") {
      connectSSE();
    }
  }, [agreement?.status]);

  async function loadAuditLog() {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/v1/negotiations/${id}/audit-log`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setAuditLog(data);
      }
    } catch {
      // audit log unavailable
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!agreement) return <div className="text-red-600">Agreement not found</div>;

  const isCompleted = agreement.status.startsWith("completed_");
  const isNegotiating = agreement.status === "confirmed" && phase && phase !== "complete";

  // Determine status step
  let statusIdx = 0;
  if (agreement.status === "confirmed") statusIdx = 1;
  if (isCompleted) statusIdx = 2;

  return (
    <div className="max-w-2xl animate-fadeIn">
      <a
        href="#/seller/agreements"
        className="text-sm text-ndai-600 hover:text-ndai-700 mb-4 inline-block"
      >
        &larr; Back to agreements
      </a>

      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">
            {agreement.invention_title || `Agreement ${agreement.id.slice(0, 8)}`}
          </h1>
          {agreement.created_at && (
            <p className="text-xs text-gray-400 mt-1">Created {timeAgo(agreement.created_at)}</p>
          )}
        </div>
        <StatusBadge status={agreement.status} />
      </div>

      {/* Status timeline */}
      <div className="flex items-center gap-1 mb-6">
        {STATUS_STEPS.map((step, i) => (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <div className={`flex-1 h-0.5 ${i <= statusIdx ? "bg-ndai-500" : "bg-gray-200"}`} />
            )}
            <div className="flex flex-col items-center gap-1">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs ${
                i < statusIdx ? "bg-ndai-500 text-white" :
                i === statusIdx ? "bg-ndai-100 text-ndai-700 ring-2 ring-ndai-500" :
                "bg-gray-100 text-gray-400"
              }`}>
                {i < statusIdx ? (
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : i + 1}
              </div>
              <span className={`text-xs ${i <= statusIdx ? "text-ndai-700 font-medium" : "text-gray-400"}`}>
                {step.label}
              </span>
            </div>
          </React.Fragment>
        ))}
      </div>

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
          <div>
            <span className="text-gray-500">Invention</span>
            <div className="mt-1 font-mono text-xs">{agreement.invention_id.slice(0, 12)}...</div>
          </div>
        </div>
      </Card>

      {/* Live negotiation progress */}
      {isNegotiating && (
        <Card className="mb-6">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="font-medium">Negotiation in progress</span>
          </div>
          <NegotiationProgress phase={phase} progressLog={progressLog} />
          <div className="text-xs text-gray-400 mt-3">
            AI agents are negotiating inside the Trusted Execution Environment
          </div>
        </Card>
      )}

      {outcome && <OutcomeDisplay outcome={outcome} />}

      <div className="mb-6">
        <MechanismExplorer
          initialBudgetCap={agreement.budget_cap ?? 0.8}
          initialAlpha0={agreement.alpha_0 ?? 0.3}
          initialOmegaHat={outcome?.omega_hat ?? 0.5}
          initialBuyerValue={outcome?.buyer_valuation ?? 0.5}
        />
      </div>

      {isCompleted && (
        <VerificationPanel verification={null} escrowData={escrowData} />
      )}

      {/* Audit Trail */}
      {isCompleted && (
        <div className="mt-6">
          <button
            onClick={() => { setShowAudit(!showAudit); if (!showAudit && auditLog.length === 0) loadAuditLog(); }}
            className="text-sm text-ndai-600 hover:text-ndai-700 flex items-center gap-1"
          >
            <svg className={`w-4 h-4 transition-transform ${showAudit ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            Audit Trail
          </button>
          {showAudit && (
            <div className="mt-3 space-y-2">
              {auditLog.length === 0 ? (
                <div className="text-sm text-gray-400">No audit entries</div>
              ) : (
                auditLog.map((e: any, i: number) => (
                  <div key={i} className="flex items-center gap-3 text-xs text-gray-600 py-1 border-b border-gray-50 last:border-0">
                    <span className="text-gray-400 w-32 flex-shrink-0">
                      {e.created_at ? new Date(e.created_at).toLocaleString() : "—"}
                    </span>
                    <span className="font-medium">{e.event_type}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
