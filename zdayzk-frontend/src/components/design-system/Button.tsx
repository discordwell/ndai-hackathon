import React from "react";
import { Spinner } from "./Spinner";

const variants = {
  primary:
    "bg-accent-400 text-surface-950 hover:bg-accent-300 active:bg-accent-500 font-semibold",
  secondary:
    "bg-surface-800 text-white border border-accent-500/30 hover:border-accent-400/60 hover:bg-surface-700",
  ghost:
    "bg-transparent text-white hover:bg-surface-800 active:bg-surface-700",
  danger:
    "bg-danger-500 text-white hover:bg-danger-400 active:bg-danger-600 font-semibold",
} as const;

const sizes = {
  sm: "px-3 py-1.5 text-xs rounded-lg gap-1.5",
  md: "px-4 py-2 text-sm rounded-lg gap-2",
  lg: "px-6 py-3 text-base rounded-xl gap-2.5",
} as const;

type ButtonProps = {
  variant?: keyof typeof variants;
  size?: keyof typeof sizes;
  disabled?: boolean;
  loading?: boolean;
  fullWidth?: boolean;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
} & Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children">;

export function Button({
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  fullWidth = false,
  icon,
  children,
  className = "",
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || loading}
      className={`
        inline-flex items-center justify-center transition-colors duration-150
        ${variants[variant]}
        ${sizes[size]}
        ${fullWidth ? "w-full" : ""}
        ${disabled || loading ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}
        ${className}
      `}
      {...props}
    >
      {loading ? (
        <Spinner size={size === "lg" ? "md" : "sm"} className={variant === "primary" ? "text-surface-950" : ""} />
      ) : icon ? (
        <span className="shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}
