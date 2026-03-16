import React from "react";

interface Props {
  finalPrice: number;
  omegaHat: number;
  buyerValuation: number | null;
}

export function PriceBreakdown({ finalPrice, omegaHat, buyerValuation }: Props) {
  const theta = omegaHat > 0 ? finalPrice / omegaHat : 0;
  // Derive alpha_0 from theta: theta = (1 + alpha_0) / 2 => alpha_0 = 2*theta - 1
  const alpha0 = Math.max(0, 2 * theta - 1);

  const isBilateral = buyerValuation !== null;

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
        {isBilateral && (
          <div className="flex justify-between">
            <span className="text-gray-500">Buyer Assessment (v_b)</span>
            <span className="font-mono">{buyerValuation.toFixed(4)}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-gray-500">
            {isBilateral ? "Seller Reserve (alpha_0)" : "Bargaining Power (theta)"}
          </span>
          <span className="font-mono">
            {isBilateral ? alpha0.toFixed(4) : theta.toFixed(4)}
          </span>
        </div>
        <div className="border-t border-gray-200 pt-2 flex justify-between font-medium">
          <span>
            {isBilateral
              ? "Final Price P* = (v_b + \u03B1\u2080\u00B7\u03C9\u0302) / 2"
              : "Final Price (P* = \u03B8 \u00B7 \u03C9\u0302)"}
          </span>
          <span className="font-mono text-ndai-700">
            {finalPrice.toFixed(4)}
          </span>
        </div>
      </div>
    </div>
  );
}
