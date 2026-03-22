import React, { useState, useEffect, useRef } from "react";
import { getVulnAgreement, startNegotiation, type VulnAgreementResponse } from "../../api/vulns";
import { LoadingSpinner } from "../../components/LoadingSpinner";
import { StatusBadge } from "../../components/StatusBadge";

export function DealPage({ id }: { id: string }) {
  const [deal, setDeal] = useState<VulnAgreementResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [negotiating, setNegotiating] = useState(false);
  const [events, setEvents] = useState<string[]>([]);
  const [error, setError] = useState("");
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getVulnAgreement(id)
      .then(setDeal)
      .catch((e) => setError(e.detail || "Failed to load"))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [events]);

  async function handleStart() {
    setNegotiating(true);
    setError("");
    try {
      await startNegotiation(id);
      setEvents((e) => [...e, "Negotiation started..."]);

      const token = localStorage.getItem("token");
      const es = new EventSource(`/api/v1/vulns/negotiations/${id}/stream?token=${token}`);
      es.addEventListener("seller_disclosure", () => setEvents((e) => [...e, "Seller agent deciding disclosure..."]));
      es.addEventListener("buyer_evaluation", () => setEvents((e) => [...e, "Buyer agent evaluating..."]));
      es.addEventListener("nash_resolution", () => setEvents((e) => [...e, "Computing Nash equilibrium..."]));
      es.addEventListener("complete", (ev: MessageEvent) => {
        const data = JSON.parse(ev.data);
        setEvents((e) => [...e, `Complete: ${data.outcome} — ${data.final_price?.toFixed(4) || "N/A"} ETH`]);
        es.close();
        setNegotiating(false);
      });
      es.addEventListener("error_event", (ev: MessageEvent) => {
        setEvents((e) => [...e, `Error: ${ev.data}`]);
        es.close();
        setNegotiating(false);
      });
      es.onerror = () => { es.close(); setNegotiating(false); };
    } catch (err: any) {
      setError(err.detail || "Failed to start negotiation");
      setNegotiating(false);
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!deal) return <div className="font-mono text-zk-danger">Deal not found</div>;

  return (
    <div className="max-w-3xl">
      <a href="#/deals" className="font-mono text-xs text-zk-muted hover:text-zk-accent mb-4 block">
        &larr; BACK TO DEALS
      </a>

      <h1 className="font-mono text-headline mb-6">DEAL</h1>

      <div className="zk-card mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <div>
            <div className="zk-label">ID</div>
            <div className="font-mono text-xs">{deal.id.slice(0, 12)}...</div>
          </div>
          <div>
            <div className="zk-label">STATUS</div>
            <StatusBadge status={deal.status} />
          </div>
          <div>
            <div className="zk-label">BUDGET CAP</div>
            <div className="font-mono text-sm font-bold">{deal.budget_cap || "—"} ETH</div>
          </div>
          <div>
            <div className="zk-label">ALPHA_0</div>
            <div className="font-mono text-sm">{deal.alpha_0 ?? "—"}</div>
          </div>
        </div>
      </div>

      {error && (
        <div className="border-2 border-zk-danger p-3 mb-6 font-mono text-sm text-zk-danger">{error}</div>
      )}

      {deal.status === "delegation_confirmed" && !negotiating && (
        <button onClick={handleStart} className="zk-btn-accent mb-6">
          START TEE NEGOTIATION
        </button>
      )}

      {negotiating && (
        <div className="font-mono text-sm text-zk-accent mb-4 animate-pulse">
          NEGOTIATION IN PROGRESS...
        </div>
      )}

      {events.length > 0 && (
        <div className="zk-card">
          <div className="zk-section-title">EVENT LOG</div>
          <div ref={logRef} className="max-h-60 overflow-y-auto font-mono text-xs space-y-1">
            {events.map((ev, i) => (
              <div key={i} className={ev.includes("Error") ? "text-zk-danger" : ev.includes("Complete") ? "text-zk-success font-bold" : "text-zk-muted"}>
                {ev}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
