import React, { useEffect, useState, useMemo } from "react";
import { listTranscripts, aggregate, TranscriptResponse, AggregationResponse } from "../../api/transcripts";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";
import { BulletList } from "../../components/shared/BulletList";
import { SectionCard } from "../../components/shared/SectionCard";
import { VerificationPanel } from "../../components/shared/VerificationPanel";

function downloadReport(result: AggregationResponse) {
  const lines = [
    `# Cross-Team Analysis Report`,
    "",
    `## Executive Summary`,
    result.cross_team_summary,
    "",
    `## Shared Dependencies`,
    ...result.shared_dependencies.map((d) => `- ${d}`),
    ...(result.shared_dependencies.length === 0 ? ["_None identified_"] : []),
    "",
    `## Shared Blockers`,
    ...result.shared_blockers.map((b) => `- ${b}`),
    ...(result.shared_blockers.length === 0 ? ["_None identified_"] : []),
    "",
    `## Recommendations`,
    ...result.recommendations.map((r) => `- ${r}`),
    ...(result.recommendations.length === 0 ? ["_None_"] : []),
    "",
    `---`,
    `_Aggregated from ${result.transcript_count} transcripts | TEE-attested analysis_`,
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `cross-team-report-${Date.now()}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export function AggregationPage() {
  const [allTranscripts, setAllTranscripts] = useState<TranscriptResponse[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<AggregationResponse | null>(null);
  const [teamFilter, setTeamFilter] = useState("all");

  useEffect(() => {
    listTranscripts(0, 100)
      .then((res) => setAllTranscripts(res.items))
      .catch((err: any) => setError(err.detail || err.message || "Failed to load transcripts"))
      .finally(() => setLoading(false));
  }, []);

  const completed = useMemo(
    () => allTranscripts.filter((t) => t.status === "completed" || t.status === "processed"),
    [allTranscripts],
  );
  const hiddenCount = allTranscripts.length - completed.length;

  const teams = useMemo(() => {
    const names = new Set(completed.map((t) => t.team_name).filter(Boolean) as string[]);
    return Array.from(names).sort();
  }, [completed]);

  const filtered = useMemo(() => {
    if (teamFilter === "all") return completed;
    return completed.filter((t) => t.team_name === teamFilter);
  }, [completed, teamFilter]);

  function handleTeamFilterChange(value: string) {
    setTeamFilter(value);
    setSelected(new Set());
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelected(new Set(filtered.map((t) => t.id)));
  }

  function deselectAll() {
    setSelected(new Set());
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
    <div className="max-w-4xl animate-[fadeSlideUp_0.4s_ease-out]">
      <h1 className="text-2xl font-bold mb-2">Cross-Team Analysis</h1>
      <p className="text-sm text-gray-500 mb-6">
        Select two or more completed transcripts to generate a cross-team intelligence report.
      </p>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : completed.length === 0 ? (
        <EmptyState
          title="No completed transcripts"
          description="Submit and wait for transcripts to finish processing before running cross-team analysis"
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
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="font-semibold text-gray-900">
                  Select Transcripts{" "}
                  <span className="text-gray-400 font-normal text-sm">
                    ({selected.size} selected)
                  </span>
                </h2>
                {hiddenCount > 0 && (
                  <p className="text-xs text-gray-400 mt-0.5">
                    {hiddenCount} transcript{hiddenCount !== 1 ? "s" : ""} hidden (not yet processed)
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {teams.length > 0 && (
                  <select
                    value={teamFilter}
                    onChange={(e) => handleTeamFilterChange(e.target.value)}
                    className="px-2 py-1 border border-gray-300 rounded-lg text-xs bg-white focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
                  >
                    <option value="all">All Teams</option>
                    {teams.map((t) => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                )}
                <button
                  type="button"
                  onClick={selectAll}
                  className="text-xs text-ndai-600 hover:text-ndai-700 font-medium"
                >
                  Select All
                </button>
                <span className="text-gray-300">|</span>
                <button
                  type="button"
                  onClick={deselectAll}
                  className="text-xs text-gray-500 hover:text-gray-700 font-medium"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="space-y-2">
              {filtered.map((t, i) => (
                <label
                  key={t.id}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all animate-[fadeSlideUp_0.3s_ease-out] ${
                    selected.has(t.id)
                      ? "border-ndai-500 bg-ndai-50 border-l-4 border-l-ndai-500"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                  style={{
                    animationDelay: `${Math.min(i, 10) * 40}ms`,
                    animationFillMode: "both",
                  }}
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
                      <p className="text-xs text-gray-500">
                        <span className="inline-block bg-gray-50 text-gray-600 px-1.5 py-0.5 rounded text-xs font-medium">
                          {t.team_name}
                        </span>
                      </p>
                    )}
                  </div>
                  <span className="text-xs text-gray-400 shrink-0">{new Date(t.created_at).toLocaleDateString()}</span>
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
            className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm transition-colors"
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
        <div className="mt-8 space-y-6 animate-[scaleIn_0.3s_ease-out]">
          <div className="flex items-center justify-between">
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
            <button
              onClick={() => downloadReport(result)}
              className="px-3 py-1.5 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-xs font-medium transition-colors"
            >
              Download Report
            </button>
          </div>

          <div className="bg-white rounded-xl border border-gray-100 p-6">
            <h3 className="font-semibold text-gray-900 mb-3">Executive Summary</h3>
            <p className="text-sm text-gray-700 leading-relaxed">{result.cross_team_summary}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <SectionCard title="Shared Dependencies" icon={<span>&#x1F517;</span>} padding="sm">
              <BulletList items={result.shared_dependencies} emptyText="None identified" />
            </SectionCard>
            <SectionCard title="Shared Blockers" icon={<span>&#x26A0;</span>} padding="sm">
              <BulletList items={result.shared_blockers} emptyText="None identified" />
            </SectionCard>
            <SectionCard title="Recommendations" icon={<span>&#x1F4A1;</span>} padding="sm">
              <BulletList items={result.recommendations} emptyText="None" />
            </SectionCard>
          </div>

          <VerificationPanel verification={result.verification} />
        </div>
      )}
    </div>
  );
}
