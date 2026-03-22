import React from "react";

const variants = {
  default: "bg-surface-700/60 text-surface-600 text-white/80",
  accent: "bg-accent-400/15 text-accent-400 border border-accent-400/20",
  danger: "bg-danger-500/15 text-danger-400 border border-danger-500/20",
  success: "bg-success-500/15 text-success-400 border border-success-500/20",
  info: "bg-info-500/15 text-info-400 border border-info-500/20",
} as const;

const sizes = {
  sm: "px-2 py-0.5 text-[10px]",
  md: "px-2.5 py-1 text-xs",
} as const;

type BadgeProps = {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  className?: string;
  children: React.ReactNode;
};

export function Badge({
  variant = "default",
  size = "md",
  className = "",
  children,
}: BadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center rounded-full font-medium leading-none
        ${variants[variant]}
        ${sizes[size]}
        ${className}
      `}
    >
      {children}
    </span>
  );
}
