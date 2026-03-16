import React from "react";

interface Props {
  finalPrice: number;
  omegaHat: number;
  buyerValuation: number | null;
}

export function PriceBreakdown({ finalPrice, omegaHat, buyerValuation }: Props) {
  const isBilateral = buyerValuation !== null;
  // In bilateral mode: P = (v_b + alpha_0 * omega_hat) / 2
  // So alpha_0 * omega_hat = 2P - v_b (seller reservation component)
  const sellerReservation = isBilateral ? 2 * finalPrice - buyerValuation : null;

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h4 className="text-sm font-medium text-gray-700 mb-3">
        Price Breakdown
      </h4>
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">Disclosed Value (&omega;&#x0302;)</span>
          <span className="font-mono">{omegaHat.toFixed(4)}</span>
        </div>
        {isBilateral && (
          <>
            <div className="flex justify-between">
              <span className="text-gray-500">Buyer Assessment (v_b)</span>
              <span className="font-mono">{buyerValuation.toFixed(4)}</span>
            </div>
            {sellerReservation !== null && (
              <div className="flex justify-between">
                <span className="text-gray-500">
                  Seller Reservation (&alpha;&#x2080;&middot;&omega;&#x0302;)
                </span>
                <span className="font-mono">{sellerReservation.toFixed(4)}</span>
              </div>
            )}
          </>
        )}
        {!isBilateral && (
          <div className="flex justify-between">
            <span className="text-gray-500">Bargaining Power (&theta;)</span>
            <span className="font-mono">
              {omegaHat > 0 ? (finalPrice / omegaHat).toFixed(4) : "0.0000"}
            </span>
          </div>
        )}
        <div className="border-t border-gray-200 pt-2 flex justify-between font-medium">
          <span>
            {isBilateral
              ? "Final Price P* = (v\u2082 + \u03B1\u2080\u00B7\u03C9\u0302) / 2"
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
