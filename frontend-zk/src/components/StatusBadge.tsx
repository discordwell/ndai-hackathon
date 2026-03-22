import React from "react";

const STATUS_STYLES: Record<string, string> = {
  active: "border-zk-success text-zk-success",
  fulfilled: "border-zk-link text-zk-link",
  expired: "border-zk-dim text-zk-dim",
  cancelled: "border-zk-dim text-zk-dim line-through",
  pending: "border-zk-warn text-zk-warn",
  accepted: "border-zk-success text-zk-success",
  rejected: "border-zk-danger text-zk-danger",
  withdrawn: "border-zk-dim text-zk-dim",
  proposed: "border-zk-warn text-zk-warn",
  completed: "border-zk-success text-zk-success",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || "border-zk-border text-zk-text";
  return (
    <span className={`zk-tag ${style}`}>
      {status}
    </span>
  );
}
