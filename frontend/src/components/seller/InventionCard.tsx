import React from "react";
import { Card } from "../shared/Card";
import { StatusBadge } from "../shared/StatusBadge";
import type { InventionResponse } from "../../api/types";

export function InventionCard({ invention }: { invention: InventionResponse }) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{invention.title}</h3>
          {invention.anonymized_summary && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">
              {invention.anonymized_summary}
            </p>
          )}
          {invention.category && (
            <span className="inline-block mt-2 text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
              {invention.category}
            </span>
          )}
        </div>
        <StatusBadge status={invention.status} />
      </div>
    </Card>
  );
}
