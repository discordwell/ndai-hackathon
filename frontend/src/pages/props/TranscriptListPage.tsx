import React, { useEffect, useState, useMemo } from "react";
import { listTranscripts, TranscriptResponse } from "../../api/transcripts";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";

function statusColor(status: string) {
  switch (status) {
    case "processed":
    case "completed":
      return "bg-green-100 text-green-700";
    case "submitted":
    case "processing":
      return "bg-blue-100 text-blue-700";
    case "failed":
    case "error":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

const PAGE_SIZE = 25;

export function TranscriptListPage() {
  const [transcripts, setTranscripts] = useState<TranscriptResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [teamFilter, setTeamFilter] = useState("all");
  async function fetchPage(pageOffset: number) {
    try {
      const res = await listTranscripts(pageOffset, PAGE_SIZE);
      setTranscripts(res.items);
      setTotal(res.total);
      setOffset(pageOffset);
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to load transcripts");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchPage(0);
  }, []);

  // Auto-refresh when processing items exist (recursive setTimeout to avoid interval stacking)
  useEffect(() => {
    const hasProcessing = transcripts.some((t) => t.status === "submitted" || t.status === "processing");
    if (!hasProcessing) return;

    const timer = setTimeout(async () => {
      try {
        const res = await listTranscripts(offset, PAGE_SIZE);
        setTranscripts(res.items);
        setTotal(res.total);
      } catch {
        // Silently retry on next cycle
      }
    }, 5000);

    return () => clearTimeout(timer);
  }, [transcripts, offset]);

  const teams = useMemo(() => {
    const names = new Set(transcripts.map((t) => t.team_name).filter(Boolean) as string[]);
    return Array.from(names).sort();
  }, [transcripts]);

  const filtered = useMemo(() => {
    return transcripts.filter((t) => {
      if (statusFilter !== "all" && t.status !== statusFilter) return false;
      if (teamFilter !== "all" && t.team_name !== teamFilter) return false;
      if (search) {
        const q = search.toLowerCase();
        if (!t.title.toLowerCase().includes(q) && !(t.team_name || "").toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [transcripts, statusFilter, teamFilter, search]);

  const totalPages = Math.ceil(total / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="animate-[fadeSlideUp_0.4s_ease-out]">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">My Transcripts</h1>
          {total > 0 && <p className="text-sm text-gray-500 mt-0.5">{total} transcript{total !== 1 ? "s" : ""}</p>}
        </div>
        <div className="flex items-center gap-3">
          <a
            href="#/props/aggregate"
            className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 text-sm font-medium transition-colors"
          >
            Cross-Team Analysis
          </a>
          <a
            href="#/props/submit"
            className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium transition-colors"
          >
            Submit Transcript
          </a>
        </div>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : transcripts.length === 0 ? (
        <EmptyState
          title="No transcripts yet"
          description="Submit your first meeting transcript to get an AI-powered summary"
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
        <>
          {/* Filters */}
          <div className="flex flex-wrap items-center gap-3 mb-5">
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title or team..."
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm w-64"
            />
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm bg-white"
            >
              <option value="all">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="submitted">Submitted</option>
              <option value="processing">Processing</option>
              <option value="error">Error</option>
            </select>
            {teams.length > 0 && (
              <select
                value={teamFilter}
                onChange={(e) => setTeamFilter(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm bg-white"
              >
                <option value="all">All Teams</option>
                {teams.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            )}
            {(search || statusFilter !== "all" || teamFilter !== "all") && (
              <span className="text-xs text-gray-400 self-center">
                {filtered.length} of {transcripts.length} on this page
              </span>
            )}
          </div>

          {/* Transcript list */}
          <div className="space-y-3">
            {filtered.map((t, i) => {
              const isProcessing = t.status === "submitted" || t.status === "processing";
              return (
                <div
                  key={t.id}
                  className="bg-white rounded-xl border border-gray-100 p-5 animate-[fadeSlideUp_0.3s_ease-out]"
                  style={{
                    animationDelay: `${Math.min(i, 10) * 50}ms`,
                    animationFillMode: "both",
                  }}
                >
                  <div className="flex items-start justify-between">
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-gray-900">{t.title}</h3>
                      {t.team_name && (
                        <p className="text-sm text-gray-500 mt-0.5">
                          <span className="inline-block bg-gray-50 text-gray-600 px-1.5 py-0.5 rounded text-xs font-medium">
                            {t.team_name}
                          </span>
                        </p>
                      )}
                    </div>
                    <span className={`text-xs px-2 py-1 rounded-full font-medium shrink-0 ml-3 ${statusColor(t.status)}`}>
                      {isProcessing && (
                        <span className="inline-block w-2 h-2 bg-current rounded-full mr-1.5 animate-pulse" />
                      )}
                      {t.status}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between">
                    <span className="text-xs text-gray-400">
                      {new Date(t.created_at).toLocaleString()}
                    </span>
                    {isProcessing ? (
                      <span className="text-xs text-blue-600 font-medium">Processing...</span>
                    ) : t.status === "completed" || t.status === "processed" ? (
                      <a
                        href={`#/props/${t.id}/summary`}
                        className="px-3 py-1.5 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-xs font-medium transition-colors"
                      >
                        View Summary
                      </a>
                    ) : (
                      <span className="text-xs text-red-500 font-medium">Failed</span>
                    )}
                  </div>
                </div>
              );
            })}
            {filtered.length === 0 && (
              <p className="text-sm text-gray-500 text-center py-8">No transcripts match your filters.</p>
            )}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-100">
              <span className="text-sm text-gray-500">
                Showing {offset + 1}–{Math.min(offset + PAGE_SIZE, total)} of {total}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => fetchPage(Math.max(0, offset - PAGE_SIZE))}
                  disabled={offset === 0}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-500 px-2">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => fetchPage(offset + PAGE_SIZE)}
                  disabled={offset + PAGE_SIZE >= total}
                  className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
