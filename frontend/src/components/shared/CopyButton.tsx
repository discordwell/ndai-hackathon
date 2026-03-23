import React, { useState } from "react";

interface CopyButtonProps {
  value: string;
  label?: string;
  truncateLength?: number;
}

export function CopyButton({ value, label, truncateLength = 16 }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }).catch(() => {
      // Fallback for non-HTTPS or unfocused contexts
      const textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }

  const display = label || (value.length > truncateLength ? value.slice(0, truncateLength) + "..." : value);

  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1 group cursor-pointer"
      title="Click to copy"
    >
      <code className="text-xs bg-gray-50 px-2 py-0.5 rounded font-mono text-gray-600 group-hover:bg-gray-100 transition-colors">
        {display}
      </code>
      {copied ? (
        <span className="text-green-500 text-xs">&#x2713;</span>
      ) : (
        <span className="text-gray-300 group-hover:text-gray-500 text-xs transition-colors">&#x2398;</span>
      )}
    </button>
  );
}
