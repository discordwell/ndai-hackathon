import React from "react";

const paddings = {
  sm: "p-3",
  md: "p-5",
  lg: "p-7",
} as const;

type CardProps = {
  hoverable?: boolean;
  glowing?: boolean;
  padding?: keyof typeof paddings;
  className?: string;
  children: React.ReactNode;
};

export function Card({
  hoverable = false,
  glowing = false,
  padding = "md",
  className = "",
  children,
}: CardProps) {
  return (
    <div
      className={`
        ${hoverable ? "glass-card-hover" : "glass-card"}
        ${glowing ? "gold-glow" : ""}
        ${paddings[padding]}
        ${className}
      `}
    >
      {children}
    </div>
  );
}
