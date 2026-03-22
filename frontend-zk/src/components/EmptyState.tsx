import React from "react";

export function EmptyState({
  message,
  action,
}: {
  message: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="border-2 border-dashed border-zk-border p-12 text-center">
      <p className="font-mono text-sm text-zk-muted uppercase">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
