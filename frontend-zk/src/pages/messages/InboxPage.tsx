import React, { useState, useEffect } from "react";
import { listConversations, type ConversationResponse } from "../../api/messaging";

export function InboxPage() {
  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listConversations()
      .then(setConversations)
      .catch((e) => setError(e.detail || "Failed to load conversations"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-5 h-5 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold text-white">Messages</h1>
        <a
          href="#/messages/new"
          className="px-3 py-1.5 text-xs font-medium bg-accent-500/20 border border-accent-500/30 text-accent-400 rounded-lg hover:bg-accent-500/30 transition-all"
        >
          + New Message
        </a>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-xs rounded-lg">
          {error}
        </div>
      )}

      <div className="flex items-center gap-2 mb-4 px-3 py-2 bg-void-800/50 rounded-lg border border-void-700/30">
        <svg className="w-3.5 h-3.5 text-accent-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
        <span className="text-[11px] text-gray-500">
          End-to-end encrypted. The platform cannot read your messages.
        </span>
      </div>

      {conversations.length === 0 ? (
        <div className="text-center py-16">
          <p className="text-gray-500 text-sm mb-2">No conversations yet</p>
          <p className="text-gray-600 text-xs">Start a conversation from a deal page or send a direct message.</p>
        </div>
      ) : (
        <div className="space-y-1">
          {conversations.map((conv) => (
            <a
              key={conv.id}
              href={`#/messages/${conv.id}`}
              className="flex items-center justify-between p-4 rounded-xl border border-void-700/30 hover:border-void-600 hover:bg-void-800/30 transition-all block"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-full bg-void-700 flex items-center justify-center flex-shrink-0">
                  <span className="text-[10px] font-mono text-gray-400">
                    {conv.type === "deal" ? "D" : "M"}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-200 truncate">
                    {conv.type === "deal" ? `Deal: ${conv.agreement_id?.slice(0, 12)}...` : `${conv.participant_a.slice(0, 8)}...↔${conv.participant_b.slice(0, 8)}...`}
                  </p>
                  <p className="text-[11px] text-gray-500 truncate">
                    {conv.type === "deal" ? "Deal conversation" : "Direct message"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {conv.unread_count > 0 && (
                  <span className="w-5 h-5 rounded-full bg-accent-400 text-void-950 text-[10px] font-bold flex items-center justify-center">
                    {conv.unread_count}
                  </span>
                )}
                <span className="text-[10px] text-gray-600">
                  {conv.created_at ? new Date(conv.created_at).toLocaleDateString() : ""}
                </span>
              </div>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
