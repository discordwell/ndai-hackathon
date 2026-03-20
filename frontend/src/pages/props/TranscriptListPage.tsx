import React, { useEffect, useState } from "react";
import { listTranscripts, TranscriptResponse } from "../../api/transcripts";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";

function statusColor(status: string) {
  switch (status) {
    case "processed":
    case "completed":
      return "bg-green-100 text-green-700";
    case "processing":
      return "bg-blue-100 text-blue-700";
    case "failed":
      return "bg-red-100 text-red-700";
    default:
      return "bg-gray-100 text-gray-600";
  }
}

export function TranscriptListPage() {
  const [transcripts, setTranscripts] = useState<TranscriptResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listTranscripts()
      .then(setTranscripts)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load transcripts"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">My Transcripts</h1>
        <a
          href="#/props/submit"
          className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
        >
          Submit Transcript
        </a>
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
        <div className="space-y-4">
          {transcripts.map((t) => (
            <div key={t.id} className="bg-white rounded-xl border border-gray-100 p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="font-semibold text-gray-900">{t.title}</h3>
                  {t.team_name && (
                    <p className="text-sm text-gray-500 mt-0.5">Team: {t.team_name}</p>
                  )}
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColor(t.status)}`}>
                  {t.status}
                </span>
              </div>
              <div className="mt-2 text-xs text-gray-400">
                {new Date(t.created_at).toLocaleString()}
              </div>
              <div className="mt-4">
                <a
                  href={`#/props/${t.id}/summary`}
                  className="px-3 py-1.5 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-xs font-medium"
                >
                  View Summary
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
