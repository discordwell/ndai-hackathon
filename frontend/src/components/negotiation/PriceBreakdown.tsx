import React from "react";

interface Props {
  finalPrice: number;
  omegaHat: number;
}

export function PriceBreakdown({ finalPrice, omegaHat }: Props) {
  const theta = omegaHat > 0 ? finalPrice / omegaHat : 0;

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-3">
        Price Breakdown
      </h4>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Disclosed Value (omega-hat)</span>
          <span className="font-mono">{omegaHat.toFixed(4)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Bargaining Power (theta)</span>
          <span className="font-mono">{theta.toFixed(4)}</span>
        </div>
        <div className="border-t border-gray-200 pt-2 flex justify-between font-medium">
          <span>Final Price (P* = theta * omega-hat)</span>
          <span className="font-mono text-ndai-700">
            {finalPrice.toFixed(4)}
          </span>
        </div>
      </div>
    </div>
  );
}
