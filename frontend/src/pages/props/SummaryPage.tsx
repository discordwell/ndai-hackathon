import React, { useEffect, useState, useRef } from "react";
import { getSummary, getTranscript, TranscriptSummaryResponse } from "../../api/transcripts";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { BulletList } from "../../components/shared/BulletList";
import { SectionCard } from "../../components/shared/SectionCard";
import { VerificationPanel } from "../../components/shared/VerificationPanel";
import { PolicyDisplay } from "../../components/shared/PolicyDisplay";
import { EgressLogDisplay } from "../../components/shared/EgressLogDisplay";

interface Props {
  id: string;
}

function SentimentBadge({ sentiment }: { sentiment: string | null }) {
  if (!sentiment) return null;
  const colors: Record<string, string> = {
    positive: "bg-green-100 text-green-700",
    negative: "bg-red-100 text-red-700",
    neutral: "bg-gray-100 text-gray-600",
    mixed: "bg-yellow-100 text-yellow-700",
  };
  const color = colors[sentiment.toLowerCase()] || "bg-gray-100 text-gray-600";
  return (
    <span className={`text-xs px-2 py-1 rounded-full font-medium ${color}`}>
      {sentiment}
    </span>
  );
}

function ProcessingStepper({ status }: { status: string }) {
  const steps = [
    { label: "Submitted", key: "submitted" },
    { label: "Processing in TEE", key: "processing" },
    { label: "Summary Ready", key: "completed" },
  ];

  const currentIndex = status === "submitted" ? 0 : status === "processing" ? 1 : 2;

  return (
    <div className="max-w-md mx-auto">
      <div className="flex items-center justify-between">
        {steps.map((step, i) => {
          const done = i < currentIndex;
          const active = i === currentIndex;
          return (
            <React.Fragment key={step.key}>
              {i > 0 && (
                <div className={`flex-1 h-0.5 mx-2 transition-colors duration-500 ${done ? "bg-ndai-500" : "bg-gray-200"}`} />
              )}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-all duration-500 ${
                    done
                      ? "bg-ndai-500 text-white"
                      : active
                      ? "bg-ndai-100 text-ndai-700 ring-2 ring-ndai-400 ring-offset-2"
                      : "bg-gray-100 text-gray-400"
                  }`}
                >
                  {done ? "\u2713" : i + 1}
                </div>
                <span className={`text-xs font-medium ${done || active ? "text-gray-900" : "text-gray-400"}`}>
                  {step.label}
                </span>
              </div>
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

function ProcessingState({ id, status }: { id: string; status: string }) {
  return (
    <div className="max-w-3xl animate-[fadeSlideUp_0.4s_ease-out]">
      <div className="mb-6">
        <a href="#/props" className="text-sm text-ndai-600 hover:underline">
          &larr; My Transcripts
        </a>
      </div>
      <div className="bg-white rounded-xl border border-gray-100 p-8">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-ndai-50 mb-4">
            <div className="w-8 h-8 border-3 border-ndai-200 border-t-ndai-600 rounded-full animate-spin" />
          </div>
          <h2 className="text-lg font-semibold text-gray-900 mb-1">Processing Transcript</h2>
          <p className="text-sm text-gray-500">
            Your transcript is being analyzed inside a Trusted Execution Environment.
          </p>
        </div>
        <ProcessingStepper status={status} />
      </div>
    </div>
  );
}

function ErrorState({ message }: { message: string }) {
  return (
    <div className="max-w-3xl animate-[fadeSlideUp_0.4s_ease-out]">
      <div className="mb-6">
        <a href="#/props" className="text-sm text-ndai-600 hover:underline">
          &larr; My Transcripts
        </a>
      </div>
      <div className="bg-white rounded-xl border border-red-100 p-8 text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-red-50 mb-4">
          <span className="text-red-500 text-2xl">&times;</span>
        </div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Processing Failed</h2>
        <p className="text-sm text-gray-500 mb-4">{message}</p>
        <a
          href="#/props"
          className="inline-block px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium transition-colors"
        >
          Back to Transcripts
        </a>
      </div>
    </div>
  );
}

function downloadMarkdown(summary: TranscriptSummaryResponse) {
  const lines = [
    `# Transcript Summary`,
    "",
    `## Executive Summary`,
    summary.executive_summary,
    "",
    `**Sentiment:** ${summary.sentiment || "N/A"}`,
    "",
    `## Action Items`,
    ...summary.action_items.map((a) => `- ${a}`),
    ...(summary.action_items.length === 0 ? ["_None identified_"] : []),
    "",
    `## Key Decisions`,
    ...summary.key_decisions.map((d) => `- ${d}`),
    ...(summary.key_decisions.length === 0 ? ["_None recorded_"] : []),
    "",
    `## Dependencies`,
    ...summary.dependencies.map((d) => `- ${d}`),
    ...(summary.dependencies.length === 0 ? ["_None noted_"] : []),
    "",
    `## Blockers`,
    ...summary.blockers.map((b) => `- ${b}`),
    ...(summary.blockers.length === 0 ? ["_None identified_"] : []),
    "",
    `---`,
    `_Generated via TEE-attested analysis | ${new Date(summary.created_at).toLocaleString()}_`,
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `summary-${summary.transcript_id.slice(0, 8)}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export function SummaryPage({ id }: Props) {
  const [summary, setSummary] = useState<TranscriptSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const s = await getSummary(id);
        if (!cancelled) {
          setSummary(s);
          setLoading(false);
        }
      } catch (err: any) {
        if (cancelled) return;
        const status = err?.status || err?.response?.status;
        if (status === 404) {
          // Summary not ready — check transcript status
          try {
            const t = await getTranscript(id);
            if (cancelled) return;
            if (t.status === "completed") {
              // Race condition: completed but summary not yet queryable, retry shortly
              setTimeout(load, 1000);
              return;
            } else if (t.status === "error") {
              setError("Transcript processing failed. Please try submitting again.");
              setLoading(false);
            } else {
              // Still processing — show stepper and start polling
              setProcessingStatus(t.status);
              setLoading(false);
              pollRef.current = setInterval(async () => {
                try {
                  const updated = await getTranscript(id);
                  if (cancelled) return;
                  setProcessingStatus(updated.status);
                  if (updated.status === "completed") {
                    if (pollRef.current) clearInterval(pollRef.current);
                    try {
                      const s = await getSummary(id);
                      if (!cancelled) {
                        setSummary(s);
                        setProcessingStatus(null);
                      }
                    } catch {
                      // Summary may take a moment after status flip
                      setTimeout(async () => {
                        try {
                          const s = await getSummary(id);
                          if (!cancelled) {
                            setSummary(s);
                            setProcessingStatus(null);
                          }
                        } catch {
                          if (!cancelled) setError("Summary unavailable. Please refresh.");
                        }
                      }, 2000);
                    }
                  } else if (updated.status === "error") {
                    if (pollRef.current) clearInterval(pollRef.current);
                    if (!cancelled) {
                      setError("Transcript processing failed. Please try submitting again.");
                      setProcessingStatus(null);
                    }
                  }
                } catch {
                  // Polling error — silently retry next interval
                }
              }, 3000);
            }
          } catch {
            if (!cancelled) {
              setError("Transcript not found");
              setLoading(false);
            }
          }
        } else {
          setError(err.detail || err.message || "Failed to load summary");
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      cancelled = true;
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (processingStatus) return <ProcessingState id={id} status={processingStatus} />;
  if (error) return <ErrorState message={error} />;
  if (!summary) return null;

  return (
    <div className="max-w-3xl animate-[fadeSlideUp_0.4s_ease-out]">
      <div className="mb-6 flex items-center justify-between animate-[fadeIn_0.3s_ease-out]">
        <div className="flex items-center gap-3">
          <a href="#/props" className="text-sm text-ndai-600 hover:underline">
            &larr; My Transcripts
          </a>
          {summary.attestation_available && (
            <span className="text-xs bg-ndai-50 text-ndai-700 px-2 py-1 rounded-full font-medium">
              TEE Attested
            </span>
          )}
        </div>
        <button
          onClick={() => downloadMarkdown(summary)}
          className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-xs font-medium transition-colors"
        >
          Download Summary
        </button>
      </div>

      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-100 p-6 animate-[fadeSlideUp_0.4s_ease-out]">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">Executive Summary</h2>
            <SentimentBadge sentiment={summary.sentiment} />
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">{summary.executive_summary}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div style={{ animationDelay: "100ms", animationFillMode: "both" }} className="animate-[fadeSlideUp_0.4s_ease-out]">
            <SectionCard title="Action Items" icon={<span>&#x2611;</span>} padding="sm">
              <BulletList items={summary.action_items} emptyText="No action items identified" />
            </SectionCard>
          </div>
          <div style={{ animationDelay: "150ms", animationFillMode: "both" }} className="animate-[fadeSlideUp_0.4s_ease-out]">
            <SectionCard title="Key Decisions" icon={<span>&#x2696;</span>} padding="sm">
              <BulletList items={summary.key_decisions} emptyText="No key decisions recorded" />
            </SectionCard>
          </div>
          <div style={{ animationDelay: "200ms", animationFillMode: "both" }} className="animate-[fadeSlideUp_0.4s_ease-out]">
            <SectionCard title="Dependencies" icon={<span>&#x1F517;</span>} padding="sm">
              <BulletList items={summary.dependencies} emptyText="No dependencies noted" />
            </SectionCard>
          </div>
          <div style={{ animationDelay: "250ms", animationFillMode: "both" }} className="animate-[fadeSlideUp_0.4s_ease-out]">
            <SectionCard title="Blockers" icon={<span>&#x26A0;</span>} padding="sm">
              <BulletList items={summary.blockers} emptyText="No blockers identified" />
            </SectionCard>
          </div>
        </div>

        <PolicyDisplay report={summary.policy_report} constraints={summary.policy_constraints} />
        <VerificationPanel verification={summary.verification} />
        <EgressLogDisplay entries={summary.egress_log} />
      </div>
    </div>
  );
}
