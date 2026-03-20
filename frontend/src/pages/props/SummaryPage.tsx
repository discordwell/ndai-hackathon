import React, { useEffect, useState } from "react";
import { getSummary, TranscriptSummaryResponse } from "../../api/transcripts";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";

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

function BulletList({ items, emptyText }: { items: string[]; emptyText?: string }) {
  if (items.length === 0) {
    return <p className="text-sm text-gray-400 italic">{emptyText || "None"}</p>;
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

export function SummaryPage({ id }: Props) {
  const [summary, setSummary] = useState<TranscriptSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    getSummary(id)
      .then(setSummary)
      .catch((err: any) => setError(err.detail || err.message || "Failed to load summary"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (error) return (
    <div>
      <a href="#/props" className="text-sm text-ndai-600 hover:underline">&larr; Back</a>
      <div className="mt-4 text-red-600">{error}</div>
    </div>
  );
  if (!summary) return null;

  return (
    <div className="max-w-3xl">
      <div className="mb-6 flex items-center gap-3">
        <a href="#/props" className="text-sm text-ndai-600 hover:underline">
          &larr; My Transcripts
        </a>
        {summary.attestation_available && (
          <span className="text-xs bg-ndai-50 text-ndai-700 px-2 py-1 rounded-full font-medium">
            TEE Attested
          </span>
        )}
      </div>

      <div className="space-y-6">
        <div className="bg-white rounded-xl border border-gray-100 p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-semibold text-gray-900">Executive Summary</h2>
            <SentimentBadge sentiment={summary.sentiment} />
          </div>
          <p className="text-sm text-gray-700 leading-relaxed">{summary.executive_summary}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Action Items</h3>
            <BulletList items={summary.action_items} emptyText="No action items identified" />
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Key Decisions</h3>
            <BulletList items={summary.key_decisions} emptyText="No key decisions recorded" />
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Dependencies</h3>
            <BulletList items={summary.dependencies} emptyText="No dependencies noted" />
          </div>
          <div className="bg-white rounded-xl border border-gray-100 p-5">
            <h3 className="font-semibold text-gray-900 mb-3">Blockers</h3>
            <BulletList items={summary.blockers} emptyText="No blockers identified" />
          </div>
        </div>
      </div>
    </div>
  );
}
