import React from "react";
import { Card } from "../shared/Card";
import { StatusBadge } from "../shared/StatusBadge";
import type { InventionResponse } from "../../api/types";

export function InventionCard({ invention }: { invention: InventionResponse }) {
  return (
    <Card
      onClick={() => (window.location.hash = `#/seller/inventions/${invention.id}`)}
      className="hover:border-ndai-200 transition-colors cursor-pointer"
    >
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{invention.title}</h3>
          {invention.anonymized_summary && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">
              {invention.anonymized_summary}
            </p>
          )}
          <div className="flex items-center gap-2 mt-2">
            {invention.category && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                {invention.category}
              </span>
            )}
            {invention.development_stage && (
              <span className="text-xs text-ndai-600 bg-ndai-50 px-2 py-0.5 rounded capitalize">
                {invention.development_stage}
              </span>
            )}
          </div>
        </div>
        <StatusBadge status={invention.status} />
      </div>
    </Card>
  );
}
