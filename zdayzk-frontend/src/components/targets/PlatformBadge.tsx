import React from "react";

const PLATFORM_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  linux: {
    bg: "bg-emerald-500/15 border-emerald-500/25",
    text: "text-emerald-400",
    label: "Linux",
  },
  windows: {
    bg: "bg-blue-500/15 border-blue-500/25",
    text: "text-blue-400",
    label: "Windows",
  },
  ios: {
    bg: "bg-gray-500/15 border-gray-500/25",
    text: "text-gray-400",
    label: "iOS",
  },
};

interface Props {
  platform: string;
}

export function PlatformBadge({ platform }: Props) {
  const style = PLATFORM_STYLES[platform] || PLATFORM_STYLES.linux;
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-medium ${style.bg} ${style.text}`}
    >
      {style.label}
    </span>
  );
}
