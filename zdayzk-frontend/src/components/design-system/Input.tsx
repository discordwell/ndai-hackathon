import React from "react";

type InputProps = {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
  className?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "className">;

export function Input({
  label,
  error,
  icon,
  className = "",
  id,
  ...props
}: InputProps) {
  const inputId = id || label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && (
        <label htmlFor={inputId} className="text-sm text-white/70 font-medium">
          {label}
        </label>
      )}
      <div className="relative">
        {icon && (
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40">
            {icon}
          </span>
        )}
        <input
          id={inputId}
          className={`
            w-full bg-surface-800 border rounded-lg px-3 py-2 text-sm text-white
            placeholder:text-white/30
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-accent-400/40 focus:border-accent-400/60
            ${icon ? "pl-10" : ""}
            ${error ? "border-danger-500/60" : "border-surface-700"}
          `}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-danger-400">{error}</p>}
    </div>
  );
}
