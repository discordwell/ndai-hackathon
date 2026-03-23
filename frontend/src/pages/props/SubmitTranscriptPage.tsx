import React, { useState } from "react";
import { submitTranscript } from "../../api/transcripts";

export function SubmitTranscriptPage() {
  const [title, setTitle] = useState("");
  const [teamName, setTeamName] = useState("");
  const [content, setContent] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [pasteFlash, setPasteFlash] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const result = await submitTranscript({
        title,
        team_name: teamName || undefined,
        content,
      });
      window.location.hash = `#/props/${result.id}/summary`;
    } catch (err: any) {
      setError(err.detail || err.message || "Failed to submit transcript");
    } finally {
      setSubmitting(false);
    }
  }

  function handlePaste(e: React.ClipboardEvent) {
    const text = e.clipboardData.getData("text");
    if (text.length > 500) {
      setPasteFlash(true);
      setTimeout(() => setPasteFlash(false), 2000);
    }
  }

  const charCount = content.length;
  const charColor = charCount > 100000 ? "text-red-500" : charCount > 50000 ? "text-yellow-600" : "text-gray-400";

  return (
    <div className="max-w-3xl animate-[fadeSlideUp_0.4s_ease-out]">
      <h1 className="text-2xl font-bold mb-2">Submit Transcript</h1>
      <p className="text-sm text-gray-500 mb-6">
        Submit a meeting transcript for TEE-secured AI analysis. The raw content is destroyed after processing.
      </p>
      <div className="bg-white rounded-xl border border-gray-100 p-6">
        {error && (
          <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm mb-4">{error}</div>
        )}
        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Title</label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Q2 Planning Meeting — April 15"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Team Name <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <input
              type="text"
              value={teamName}
              onChange={(e) => setTeamName(e.target.value)}
              placeholder="e.g. Platform, Frontend, Infra"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Transcript Content</label>
            <textarea
              required
              value={content}
              onChange={(e) => setContent(e.target.value)}
              onPaste={handlePaste}
              rows={14}
              placeholder="Paste the full meeting transcript here..."
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none text-sm resize-y"
            />
            <div className="flex items-center justify-between mt-1.5">
              <p className="text-xs text-gray-400">
                Paste a full meeting transcript, chat log, or call notes.
              </p>
              <div className="flex items-center gap-2">
                {pasteFlash && (
                  <span className="text-xs text-green-600 font-medium animate-[fadeIn_0.2s_ease-out]">
                    Transcript pasted
                  </span>
                )}
                <span className={`text-xs tabular-nums ${charColor}`}>
                  {charCount.toLocaleString()} chars
                </span>
              </div>
            </div>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              type="submit"
              disabled={submitting}
              className="px-6 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium text-sm transition-colors"
            >
              {submitting ? "Submitting..." : "Submit Transcript"}
            </button>
            <a
              href="#/props"
              className="px-6 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm transition-colors"
            >
              Cancel
            </a>
          </div>
        </form>
      </div>
    </div>
  );
}
