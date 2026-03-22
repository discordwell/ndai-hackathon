import React from "react";

interface Props {
  text: string;
  timestamp: string;
  isMine: boolean;
  senderPubkey: string;
}

export function ChatBubble({ text, timestamp, isMine, senderPubkey }: Props) {
  const time = new Date(timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <div className={`flex ${isMine ? "justify-end" : "justify-start"} mb-3`}>
      <div
        className={`max-w-[75%] rounded-2xl px-4 py-2.5 ${
          isMine
            ? "bg-accent-500/20 border border-accent-500/30 text-white"
            : "bg-void-800 border border-void-700 text-gray-200"
        }`}
      >
        {!isMine && (
          <p className="text-[10px] font-mono text-gray-500 mb-1">
            {senderPubkey.slice(0, 12)}...
          </p>
        )}
        <p className="text-sm leading-relaxed whitespace-pre-wrap break-words">{text}</p>
        <p className={`text-[10px] mt-1 ${isMine ? "text-accent-500/60" : "text-gray-600"}`}>
          {time}
        </p>
      </div>
    </div>
  );
}
