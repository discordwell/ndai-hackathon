import React from "react";

type Option = {
  value: string;
  label: string;
};

type SelectProps = {
  label?: string;
  error?: string;
  options: Option[];
  placeholder?: string;
  className?: string;
} & Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "className">;

export function Select({
  label,
  error,
  options,
  placeholder,
  className = "",
  id,
  ...props
}: SelectProps) {
  const selectId = id || label?.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      {label && (
        <label htmlFor={selectId} className="text-sm text-white/70 font-medium">
          {label}
        </label>
      )}
      <div className="relative">
        <select
          id={selectId}
          className={`
            w-full appearance-none bg-surface-800 border rounded-lg px-3 py-2 pr-9 text-sm text-white
            transition-colors duration-150
            focus:outline-none focus:ring-2 focus:ring-accent-400/40 focus:border-accent-400/60
            ${error ? "border-danger-500/60" : "border-surface-700"}
          `}
          {...props}
        >
          {placeholder && (
            <option value="" disabled className="text-white/30">
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-surface-800">
              {opt.label}
            </option>
          ))}
        </select>
        <svg
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </div>
      {error && <p className="text-xs text-danger-400">{error}</p>}
    </div>
  );
}
