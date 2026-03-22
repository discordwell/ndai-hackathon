import React from "react";

interface Props {
  hasBadge: boolean;
  size?: "sm" | "md";
}

export function BadgeIndicator({ hasBadge, size = "sm" }: Props) {
  if (!hasBadge) return null;

  return (
    <span
      className={`inline-flex items-center justify-center ${
        size === "md" ? "text-base" : "text-xs"
      }`}
      title="Verified Seller"
    >
      &#9889;
    </span>
  );
}
