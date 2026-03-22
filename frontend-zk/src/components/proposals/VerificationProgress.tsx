import React, { useState, useEffect, useRef, useCallback } from "react";
import type { VerificationResult } from "../../api/types";

interface VerificationEvent {
  step: string;
  message: string;
  timestamp: number;
}

type StepStatus = "pending" | "active" | "done" | "error";

interface StepInfo {
  label: string;
  key: string;
  status: StepStatus;
}

interface Props {
  proposalId: string;
  onComplete?: (result: VerificationResult) => void;
}

export function VerificationProgress({ proposalId, onComplete }: Props) {
  const [steps, setSteps] = useState<StepInfo[]>([
    { label: "Building", key: "building", status: "pending" },
    { label: "Verifying", key: "verifying", status: "pending" },
    { label: "Result", key: "result", status: "pending" },
  ]);
  const [events, setEvents] = useState<VerificationEvent[]>([]);
  const [result, setResult] = useState<VerificationResult | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const logRef = useRef<HTMLDivElement>(null);

  const updateStep = useCallback((key: string, status: StepStatus) => {
    setSteps((prev) =>
      prev.map((s) => (s.key === key ? { ...s, status } : s))
    );
  }, []);

  useEffect(() => {
    const token = sessionStorage.getItem("zdayzk_token");
    if (!token || !proposalId) return;

    const url = `/api/v1/proposals/${proposalId}/stream?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    esRef.current = es;

    es.onopen = () => setIsConnected(true);
    es.onerror = () => setIsConnected(false);

    const addEvent = (step: string, message: string) => {
      setEvents((prev) => [...prev, { step, message, timestamp: Date.now() }]);
    };

    es.addEventListener("building", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      updateStep("building", "active");
      addEvent("building", data.message || "Building target environment...");
    });

    es.addEventListener("build_done", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      updateStep("building", "done");
      updateStep("verifying", "active");
      addEvent("building", data.message || "Build complete.");
    });

    es.addEventListener("verifying", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      addEvent("verifying", data.message || "Running verification...");
    });

    es.addEventListener("verify_done", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      updateStep("verifying", "done");
      updateStep("result", "active");
      addEvent("verifying", data.message || "Verification complete.");
    });

    es.addEventListener("result", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as VerificationResult;
      updateStep("result", data.passed ? "done" : "error");
      setResult(data);
      addEvent("result", data.passed ? "Verification passed." : `Failed: ${data.error || "Unknown error"}`);
      es.close();
      setIsConnected(false);
      onComplete?.(data);
    });

    es.addEventListener("error_event", (e) => {
      const data = JSON.parse((e as MessageEvent).data);
      setSteps((prev) =>
        prev.map((s) => (s.status === "active" ? { ...s, status: "error" } : s))
      );
      addEvent("error", data.message || "Verification error.");
      es.close();
      setIsConnected(false);
    });

    return () => {
      es.close();
    };
  }, [proposalId, updateStep, onComplete]);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="border-3 border-zk-border bg-white p-5 space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-mono font-bold text-zk-text uppercase">Verification Progress</h3>
        {isConnected && (
          <span className="flex items-center gap-1.5 text-[10px] font-mono font-bold text-emerald-600 uppercase">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live
          </span>
        )}
      </div>

      {/* Steps */}
      <div className="flex items-center gap-0">
        {steps.map((step, i) => (
          <React.Fragment key={step.key}>
            {i > 0 && (
              <div
                className={`flex-1 h-0.5 ${
                  step.status !== "pending" ? "bg-zk-accent" : "bg-zk-border"
                }`}
              />
            )}
            <div className="flex flex-col items-center gap-1.5">
              <div
                className={`w-8 h-8 flex items-center justify-center text-xs font-mono font-bold border-2 ${
                  step.status === "done"
                    ? "bg-emerald-50 text-emerald-700 border-emerald-600"
                    : step.status === "active"
                    ? "bg-zk-bg text-zk-accent border-zk-accent animate-pulse"
                    : step.status === "error"
                    ? "bg-red-50 text-red-700 border-red-600"
                    : "bg-white text-zk-dim border-zk-border"
                }`}
              >
                {step.status === "done" ? (
                  <CheckIcon />
                ) : step.status === "error" ? (
                  <XIcon />
                ) : step.status === "active" ? (
                  <SpinnerIcon />
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={`text-[10px] font-mono font-bold uppercase ${
                  step.status === "active"
                    ? "text-zk-accent"
                    : step.status === "done"
                    ? "text-emerald-700"
                    : step.status === "error"
                    ? "text-red-700"
                    : "text-zk-dim"
                }`}
              >
                {step.label}
              </span>
            </div>
          </React.Fragment>
        ))}
      </div>

      {/* Event log */}
      {events.length > 0 && (
        <div
          ref={logRef}
          className="bg-zk-bg border-2 border-zk-border p-3 max-h-48 overflow-y-auto"
        >
          {events.map((evt, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] py-0.5">
              <span className="text-zk-dim font-mono shrink-0">
                {new Date(evt.timestamp).toLocaleTimeString()}
              </span>
              <span
                className={`font-mono px-1 text-[10px] shrink-0 font-bold uppercase ${
                  evt.step === "error"
                    ? "text-red-600"
                    : "text-zk-muted"
                }`}
              >
                {evt.step}
              </span>
              <span className="text-zk-text font-mono">{evt.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Result */}
      {result && (
        <div
          className={`p-4 border-3 ${
            result.passed
              ? "border-emerald-600 bg-emerald-50"
              : "border-red-600 bg-red-50"
          }`}
        >
          <div className="flex items-center gap-2 mb-2">
            {result.passed ? (
              <span className="text-emerald-700 text-sm font-mono font-bold uppercase">Verification Passed</span>
            ) : (
              <span className="text-red-700 text-sm font-mono font-bold uppercase">Verification Failed</span>
            )}
          </div>
          <div className="space-y-1 text-xs font-mono">
            <div className="flex justify-between">
              <span className="text-zk-muted">Claimed</span>
              <span className="text-zk-text">{result.claimed_capability}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zk-muted">Verified</span>
              <span className="text-zk-text">{result.verified_capability}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zk-muted">Reliability</span>
              <span className="text-zk-accent font-bold">{(result.reliability_score * 100).toFixed(0)}%</span>
            </div>
            {result.error && (
              <p className="text-red-600 mt-2">{result.error}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  );
}

function SpinnerIcon() {
  return (
    <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
    </svg>
  );
}
