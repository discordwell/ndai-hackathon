import React from "react";

interface SectionCardProps {
  title: string;
  icon?: React.ReactNode;
  badge?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  padding?: "sm" | "md";
}

export function SectionCard({ title, icon, badge, children, className = "", padding = "md" }: SectionCardProps) {
  const pad = padding === "sm" ? "p-5" : "p-6";
  return (
    <div className={`bg-white rounded-xl border border-gray-100 ${pad} ${className}`}>
      <div className="flex items-center gap-2 mb-3">
        {icon && <span className="text-ndai-600 text-lg shrink-0">{icon}</span>}
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {badge}
      </div>
      {children}
    </div>
  );
}
