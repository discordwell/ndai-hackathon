import React from "react";

export function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="font-mono text-sm text-zk-muted animate-pulse">
        LOADING...
      </div>
    </div>
  );
}
