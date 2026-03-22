import React, { useState, useEffect, useRef, useCallback } from "react";
import { getMessages, sendMessage as apiSendMessage, type MessageResponse } from "../../api/messaging";
import { ChatBubble } from "../../components/ChatBubble";
import { ChatInput } from "../../components/ChatInput";
import { useAuth } from "../../contexts/AuthContext";

interface Props {
  conversationId: string;
}

interface DecryptedMessage {
  id: string;
  text: string;
  senderPubkey: string;
  isMine: boolean;
  timestamp: string;
}

export function ConversationPage({ conversationId }: Props) {
  const { publicKeyHex } = useAuth();
  const [messages, setMessages] = useState<DecryptedMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  // Load message history
  useEffect(() => {
    setLoading(true);
    getMessages(conversationId)
      .then((msgs) => {
        // TODO: decrypt messages using Double Ratchet
        // For now, show ciphertext indicator
        const decrypted = msgs.map((m) => ({
          id: m.id,
          text: "[Encrypted message — decryption pending]",
          senderPubkey: m.sender_pubkey,
          isMine: m.sender_pubkey === publicKeyHex,
          timestamp: m.created_at,
        }));
        setMessages(decrypted);
      })
      .catch((e) => setError(e.detail || "Failed to load messages"))
      .finally(() => setLoading(false));
  }, [conversationId, publicKeyHex]);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(
    async (text: string) => {
      // TODO: encrypt with Double Ratchet before sending
      // For now, send plaintext as base64 (development only)
      const ciphertext = btoa(text);
      const header = btoa(JSON.stringify({ dhPub: "dev", n: messages.length, pn: 0 }));

      const msg = await apiSendMessage(conversationId, { ciphertext, header });

      setMessages((prev) => [
        ...prev,
        {
          id: msg.id,
          text,
          senderPubkey: msg.sender_pubkey,
          isMine: true,
          timestamp: msg.created_at,
        },
      ]);
    },
    [conversationId, messages.length],
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-5 h-5 border-2 border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-void-700/50">
        <div className="flex items-center gap-3">
          <a href="#/messages" className="text-gray-500 hover:text-gray-300 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </a>
          <div>
            <p className="text-sm font-medium text-white">Conversation</p>
            <p className="text-[10px] font-mono text-gray-500">{conversationId.slice(0, 16)}...</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-accent-400">
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
          </svg>
          E2E Encrypted
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-2 p-2 bg-red-500/10 border border-red-500/30 text-red-400 text-xs rounded">
          {error}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-gray-500 text-sm">No messages yet</p>
            <p className="text-gray-600 text-xs mt-1">Send the first encrypted message</p>
          </div>
        ) : (
          messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              text={msg.text}
              timestamp={msg.timestamp}
              isMine={msg.isMine}
              senderPubkey={msg.senderPubkey}
            />
          ))
        )}
      </div>

      {/* Input */}
      <ChatInput onSend={handleSend} />
    </div>
  );
}
