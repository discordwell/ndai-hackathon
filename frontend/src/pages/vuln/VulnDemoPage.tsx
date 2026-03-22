import React, { useState, useEffect, useRef } from "react";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";

interface PipelinePhase {
  id: string;
  name: string;
  description: string;
  status: "pending" | "running" | "completed" | "error";
  detail?: string;
}

const INITIAL_PHASES: PipelinePhase[] = [
  { id: "verification", name: "TEE Verification", description: "Build target, plant oracles, run PoC", status: "pending" },
  { id: "negotiation", name: "AI Negotiation", description: "Nash bargaining via LLM agents", status: "pending" },
  { id: "escrow", name: "On-Chain Escrow", description: "Deploy & fund VulnEscrow on Base Sepolia", status: "pending" },
  { id: "sealed_delivery", name: "Sealed Delivery", description: "ECIES re-encryption in TEE", status: "pending" },
  { id: "settlement", name: "Settlement", description: "90/10 payment split on-chain", status: "pending" },
];

export function VulnDemoPage({ dealId }: { dealId: string }) {
  const [phases, setPhases] = useState<PipelinePhase[]>(INITIAL_PHASES);
  const [events, setEvents] = useState<string[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  function updatePhase(id: string, updates: Partial<PipelinePhase>) {
    setPhases((prev) =>
      prev.map((p) => (p.id === id ? { ...p, ...updates } : p))
    );
  }

  async function startPipeline() {
    setRunning(true);
    setError("");
    setEvents([]);
    setResult(null);
    setPhases(INITIAL_PHASES);

    const token = localStorage.getItem("ndai_token");

    try {
      // Start the pipeline
      const resp = await fetch(`/api/v1/vuln-demo/${dealId}/full-pipeline`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          agreement_id: dealId,
          budget_cap: 2.5,
          skip_verification: false,
          skip_sealed_delivery: true,
        }),
      });

      if (!resp.ok) {
        const errData = await resp.json();
        throw new Error(errData.detail || "Failed to start pipeline");
      }

      addEvent("[PIPELINE] Started");

      // Connect SSE for progress
      const sseUrl = `/api/v1/vuln-demo/${dealId}/progress?token=${token}`;
      const es = new EventSource(sseUrl);
      eventSourceRef.current = es;

      es.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          handleSSEEvent(data);
        } catch {
          // ignore parse errors
        }
      };

      es.onerror = () => {
        es.close();
        setRunning(false);
      };
    } catch (e: any) {
      setError(e.message);
      setRunning(false);
    }
  }

  function handleSSEEvent(data: any) {
    const event = data.event;

    switch (event) {
      case "phase_start":
        updatePhase(data.phase, { status: "running" });
        addEvent(`[${data.phase?.toUpperCase()}] ${data.description}`);
        break;

      case "phase_complete":
        updatePhase(data.phase, {
          status: "completed",
          detail: formatPhaseDetail(data),
        });
        addEvent(`[${data.phase?.toUpperCase()}] Complete`);
        break;

      case "verification_step":
        addEvent(`[ENCLAVE] ${data.step}`);
        break;

      case "negotiation_step":
        addEvent(`[NEGOTIATION] ${data.step}`);
        break;

      case "pipeline_complete":
        setResult(data);
        setRunning(false);
        addEvent("[PIPELINE] Complete");
        eventSourceRef.current?.close();
        break;

      case "pipeline_error":
        setError(data.error || "Pipeline failed");
        setRunning(false);
        addEvent(`[ERROR] ${data.error}`);
        eventSourceRef.current?.close();
        break;

      case "heartbeat":
        break;

      default:
        addEvent(`[${event}] ${JSON.stringify(data)}`);
    }
  }

  function addEvent(msg: string) {
    const ts = new Date().toLocaleTimeString();
    setEvents((prev) => [...prev, `${ts} ${msg}`]);
  }

  function formatPhaseDetail(data: any): string {
    if (data.phase === "verification") {
      return `Claimed: ${data.claimed} → Verified: ${data.verified} (${Math.round((data.reliability || 0) * 100)}%)`;
    }
    if (data.phase === "negotiation") {
      return `${data.outcome}: ${data.final_price?.toFixed(4) || "N/A"} ETH (${data.rounds} rounds)`;
    }
    if (data.phase === "sealed_delivery") {
      return `Hash: ${data.delivery_hash}`;
    }
    return JSON.stringify(data);
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
            CVE-2024-3094 — XZ Utils Backdoor
          </h1>
          <span style={{
            background: "#dc2626",
            color: "white",
            padding: "2px 8px",
            borderRadius: 4,
            fontSize: 13,
            fontWeight: 600,
          }}>
            CVSS 10.0
          </span>
        </div>
        <p style={{ color: "#6b7280", margin: 0, fontSize: 14 }}>
          Pre-authentication RCE via backdoored liblzma in OpenSSH.
          Full marketplace lifecycle demo.
        </p>
      </div>

      {/* Pipeline phases */}
      <div style={{
        background: "#111827",
        borderRadius: 8,
        padding: 20,
        marginBottom: 24,
      }}>
        <h2 style={{ fontSize: 16, fontWeight: 600, marginTop: 0, marginBottom: 16, color: "#e5e7eb" }}>
          Marketplace Pipeline
        </h2>
        {phases.map((phase, i) => (
          <div
            key={phase.id}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              padding: "10px 0",
              borderBottom: i < phases.length - 1 ? "1px solid #1f2937" : "none",
            }}
          >
            {/* Status indicator */}
            <div style={{ paddingTop: 2 }}>
              {phase.status === "pending" && (
                <div style={{ width: 18, height: 18, borderRadius: "50%", border: "2px solid #374151" }} />
              )}
              {phase.status === "running" && (
                <div style={{
                  width: 18, height: 18, borderRadius: "50%",
                  border: "2px solid #3b82f6",
                  borderTopColor: "transparent",
                  animation: "spin 1s linear infinite",
                }} />
              )}
              {phase.status === "completed" && (
                <div style={{
                  width: 18, height: 18, borderRadius: "50%",
                  background: "#10b981",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "white", fontSize: 11, fontWeight: 700,
                }}>
                  ✓
                </div>
              )}
              {phase.status === "error" && (
                <div style={{
                  width: 18, height: 18, borderRadius: "50%",
                  background: "#ef4444",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "white", fontSize: 11, fontWeight: 700,
                }}>
                  ✗
                </div>
              )}
            </div>

            {/* Phase info */}
            <div style={{ flex: 1 }}>
              <div style={{
                fontWeight: 600,
                fontSize: 14,
                color: phase.status === "pending" ? "#6b7280" : "#e5e7eb",
              }}>
                {phase.name}
              </div>
              <div style={{ fontSize: 12, color: "#9ca3af" }}>
                {phase.description}
              </div>
              {phase.detail && (
                <div style={{
                  fontSize: 12,
                  color: "#10b981",
                  marginTop: 4,
                  fontFamily: "monospace",
                }}>
                  {phase.detail}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Start button */}
      {!running && !result && (
        <button
          onClick={startPipeline}
          style={{
            width: "100%",
            padding: "12px 0",
            background: "#3b82f6",
            color: "white",
            border: "none",
            borderRadius: 8,
            fontSize: 16,
            fontWeight: 600,
            cursor: "pointer",
            marginBottom: 24,
          }}
        >
          Start Demo Pipeline
        </button>
      )}

      {running && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          justifyContent: "center",
          marginBottom: 24,
          color: "#3b82f6",
        }}>
          <LoadingSpinner size={16} />
          Pipeline running...
        </div>
      )}

      {/* Result */}
      {result && (
        <div style={{
          background: "#064e3b",
          borderRadius: 8,
          padding: 16,
          marginBottom: 24,
          border: "1px solid #10b981",
        }}>
          <h3 style={{ margin: "0 0 8px", fontSize: 14, fontWeight: 600, color: "#10b981" }}>
            Deal Complete
          </h3>
          <div style={{ fontSize: 13, color: "#d1fae5", fontFamily: "monospace" }}>
            <div>Outcome: {result.outcome}</div>
            {result.final_price && <div>Price: {result.final_price.toFixed(4)} ETH</div>}
            {result.rounds && <div>Rounds: {result.rounds}</div>}
            {result.verification && (
              <div>Verification: {result.verification.verified} ({Math.round(result.verification.reliability * 100)}% reliable)</div>
            )}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          background: "#7f1d1d",
          borderRadius: 8,
          padding: 16,
          marginBottom: 24,
          border: "1px solid #ef4444",
          color: "#fecaca",
          fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Event log */}
      <div style={{
        background: "#0a0a0a",
        borderRadius: 8,
        padding: 16,
      }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 14, fontWeight: 600, color: "#6b7280" }}>
          Event Log
        </h3>
        <div
          ref={logRef}
          style={{
            maxHeight: 300,
            overflowY: "auto",
            fontFamily: "monospace",
            fontSize: 12,
            lineHeight: "20px",
            color: "#d1d5db",
          }}
        >
          {events.length === 0 && (
            <div style={{ color: "#4b5563" }}>
              Waiting for pipeline to start...
            </div>
          )}
          {events.map((ev, i) => (
            <div key={i} style={{
              color: ev.includes("[ERROR]")
                ? "#ef4444"
                : ev.includes("Complete")
                  ? "#10b981"
                  : ev.includes("[ENCLAVE]")
                    ? "#3b82f6"
                    : "#d1d5db",
            }}>
              {ev}
            </div>
          ))}
        </div>
      </div>

      {/* CSS animation for spinner */}
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
