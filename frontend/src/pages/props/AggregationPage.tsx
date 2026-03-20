import React, { useEffect, useState } from "react";
import { listTranscripts, aggregate, TranscriptResponse, AggregationResponse } from "../../api/transcripts";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";
import { VerificationPanel } from "../../components/shared/VerificationPanel";

function BulletList({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-400 italic">None identified</p>;
  }
  return (
    <ul className="space-y-1">
      {items.map((item, i) => (
        <li key={i} className="flex gap-2 text-sm text-gray-700">
          <span className="text-ndai-600 mt-0.5">•</span>
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function AggregationPage() {
  const [transcripts, setTranscripts] = useState<TranscriptResponse[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<AggregationResponse | null>(null);

  useEffect(() => {
    listTranscripts()
      .then(setTranscripts)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load transcripts"))
      .finally(() => setLoading(false));
  }, []);

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleAggregate(e: React.FormEvent) {
    e.preventDefault();
    if (selected.size < 2) return;
    setSubmitting(true);
    setSubmitError("");
    setResult(null);
    try {
      const res = await aggregate(Array.from(selected));
      setResult(res);
    } catch (err: any) {
      setSubmitError(err.detail || err.message || "Aggregation failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <h1 className="text-2xl font-bold mb-2">Cross-Team Analysis</h1>
      <p className="text-sm text-gray-500 mb-6">
        Select two or more transcripts to generate a cross-team intelligence report.
      </p>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : transcripts.length === 0 ? (
        <EmptyState
          title="No transcripts available"
          description="Submit some transcripts first before running cross-team analysis"
          action={
            <a
              href="#/props/submit"
              className="inline-block px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
            >
              Submit Transcript
            </a>
          }
        />
      ) : (
        <form onSubmit={handleAggregate} className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h2 className="font-semibold text-gray-900 mb-4">
              Select Transcripts{" "}
              <span className="text-gray-400 font-normal text-sm">
                ({selected.size} selected)
              </span>
            </h2>
            <div className="space-y-2">
              {transcripts.map((t) => (
                <label
                  key={t.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selected.has(t.id)
                      ? "border-ndai-500 bg-ndai-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selected.has(t.id)}
                    onChange={() => toggleSelect(t.id)}
                    className="rounded border-gray-300 text-ndai-600 focus:ring-ndai-500"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{t.title}</p>
                    {t.team_name && (
                      <p className="text-xs text-gray-500">Team: {t.team_name}</p>
                    )}
                  </div>
                  <span className="text-xs text-gray-400">{new Date(t.created_at).toLocaleDateString()}</span>
                </label>
              ))}
            </div>
          </div>

          {submitError && (
            <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm">{submitError}</div>
          )}

          <button
            type="submit"
            disabled={submitting || selected.size < 2}
            className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm"
          >
            {submitting
              ? "Analyzing..."
              : selected.size < 2
              ? `Select at least 2 transcripts (${selected.size} selected)`
              : `Analyze ${selected.size} Transcripts`}
          </button>
        </form>
      )}

      {result && (
        <div className="mt-8 space-y-6">
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold">Cross-Team Report</h2>
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
              {result.transcript_count} transcripts
            </span>
            {result.attestation_available && (
              <span className="text-xs bg-ndai-50 text-ndai-700 px-2 py-1 rounded-full font-medium">
                TEE Attested
              </span>
            )}
          </div>

          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <h3 className="font-semibold text-gray-900 mb-3">Executive Summary</h3>
            <p className="text-sm text-gray-700 leading-relaxed">{result.cross_team_summary}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Shared Dependencies</h3>
              <BulletList items={result.shared_dependencies} />
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Shared Blockers</h3>
              <BulletList items={result.shared_blockers} />
            </div>
            <div className="bg-white rounded-xl border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3">Recommendations</h3>
              <BulletList items={result.recommendations} />
            </div>
          </div>

          <VerificationPanel verification={result.verification} />
        </div>
      )}
    </div>
  );
}
