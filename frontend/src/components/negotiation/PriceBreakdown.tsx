import React from "react";

interface Props {
  finalPrice: number;
  reason: string | null;
  rounds: number | null;
}

export function PriceBreakdown({ finalPrice, reason, rounds }: Props) {
  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-3">
        Price Breakdown
      </h4>
      <div className="space-y-2 text-sm">
        <div className="border-t border-gray-200 pt-2 flex justify-between font-medium">
          <span>Final Price (P*)</span>
          <span className="font-mono text-ndai-700">
            {finalPrice.toFixed(4)}
          </span>
        </div>
        {rounds !== null && rounds > 1 && (
          <div className="flex justify-between">
            <span className="text-gray-500">Negotiation Rounds</span>
            <span className="font-mono">{rounds}</span>
          </div>
        )}
        {reason && (
          <div className="text-xs text-gray-500 mt-2 italic">{reason}</div>
        )}
      </div>
    </div>
  );
}
