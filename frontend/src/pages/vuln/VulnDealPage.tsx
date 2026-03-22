import React, { useState, useEffect, useRef } from "react";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import {
  getVulnAgreement,
  startVulnNegotiation,
  getVulnNegotiationStatus,
  type VulnAgreementResponse,
} from "../../api/vulns";

export function VulnDealPage({ dealId }: { dealId: string }) {
  const [agreement, setAgreement] = useState<VulnAgreementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [negotiating, setNegotiating] = useState(false);
  const [outcome, setOutcome] = useState<any>(null);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getVulnAgreement(dealId)
      .then(setAgreement)
      .catch((e) => setError(e.detail || "Failed to load"))
      .finally(() => setLoading(false));
  }, [dealId]);

  async function handleStart() {
    setNegotiating(true);
    setError("");
    setEvents([]);
    setOutcome(null);

    try {
      await startVulnNegotiation(dealId);
      setEvents((e) => [...e, "Negotiation started..."]);

      // Connect SSE
      const token = localStorage.getItem("ndai_token");
      const url = `/api/v1/vulns/negotiations/${dealId}/stream?token=${token}`;
      const es = new EventSource(url);
      eventSourceRef.current = es;

      es.addEventListener("started", () => {
        setEvents((e) => [...e, "Session initialized"]);
      });
      es.addEventListener("seller_disclosure", () => {
        setEvents((e) => [...e, "Seller agent deciding disclosure level..."]);
      });
      es.addEventListener("buyer_evaluation", () => {
        setEvents((e) => [...e, "Buyer agent evaluating vulnerability..."]);
      });
      es.addEventListener("round", (ev: MessageEvent) => {
        const data = JSON.parse(ev.data);
        setEvents((e) => [
          ...e,
          `Round ${data.number}: ${data.phase}`,
        ]);
      });
      es.addEventListener("nash_resolution", () => {
        setEvents((e) => [...e, "Computing Nash equilibrium..."]);
      });
      es.addEventListener("complete", (ev: MessageEvent) => {
        const data = JSON.parse(ev.data);
        setOutcome(data);
        setNegotiating(false);
        es.close();
      });
      es.onerror = () => {
        // SSE disconnected — poll for result
        es.close();
        pollForResult();
      };
    } catch (err: any) {
      setError(err.detail || "Failed to start negotiation");
      setNegotiating(false);
    }
  }

  async function pollForResult() {
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const status = await getVulnNegotiationStatus(dealId);
        if (status.status === "completed") {
          setOutcome(status.outcome);
          setNegotiating(false);
          return;
        }
        if (status.status === "error") {
          setError(status.error || "Negotiation failed");
          setNegotiating(false);
          return;
        }
      } catch {
        // keep polling
      }
    }
    setError("Negotiation timed out");
    setNegotiating(false);
  }

  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error && !agreement) return <div className="text-red-600">{error}</div>;
  if (!agreement) return <div className="text-gray-500">Agreement not found</div>;

  const isCompleted = agreement.status.startsWith("completed_");

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Vulnerability Deal</h1>

      <div className="bg-white rounded-xl border border-gray-100 p-6 mb-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Status</span>
            <p className="font-medium">{agreement.status}</p>
          </div>
          <div>
            <span className="text-gray-500">Budget Cap</span>
            <p className="font-medium">{agreement.budget_cap}</p>
          </div>
          <div>
            <span className="text-gray-500">Alpha_0</span>
            <p className="font-medium">{agreement.alpha_0}</p>
          </div>
          <div>
            <span className="text-gray-500">Deal ID</span>
            <p className="font-mono text-xs">{dealId.slice(0, 16)}...</p>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 text-red-700 p-3 rounded-lg mb-4 text-sm">{error}</div>
      )}

      {!isCompleted && !outcome && (
        <button
          onClick={handleStart}
          disabled={negotiating}
          className="w-full py-2.5 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium mb-6"
        >
          {negotiating ? "Negotiating..." : "Start TEE Negotiation"}
        </button>
      )}

      {events.length > 0 && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 mb-6">
          <h3 className="text-sm font-medium mb-2 text-gray-700">Live Progress</h3>
          <div className="space-y-1">
            {events.map((e, i) => (
              <div key={i} className="text-xs text-gray-600 font-mono">
                {e}
              </div>
            ))}
            {negotiating && (
              <div className="text-xs text-ndai-600 animate-pulse">Processing...</div>
            )}
          </div>
        </div>
      )}

      {outcome && (
        <div
          className={`rounded-xl border p-6 ${
            outcome.outcome === "agreement"
              ? "bg-green-50 border-green-200"
              : "bg-yellow-50 border-yellow-200"
          }`}
        >
          <h3 className="font-semibold text-lg mb-3">
            {outcome.outcome === "agreement" ? "Deal Reached" : "No Deal"}
          </h3>
          <div className="grid grid-cols-2 gap-3 text-sm">
            {outcome.final_price !== null && (
              <div>
                <span className="text-gray-500">Final Price</span>
                <p className="font-bold text-lg">{outcome.final_price.toFixed(4)}</p>
              </div>
            )}
            {outcome.disclosure_level !== null && (
              <div>
                <span className="text-gray-500">Disclosure Level</span>
                <p className="font-medium">{outcome.disclosure_level}/3</p>
              </div>
            )}
            {outcome.negotiation_rounds && (
              <div>
                <span className="text-gray-500">Rounds</span>
                <p className="font-medium">{outcome.negotiation_rounds}</p>
              </div>
            )}
            {outcome.reason && (
              <div className="col-span-2">
                <span className="text-gray-500">Reason</span>
                <p className="text-sm">{outcome.reason}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
