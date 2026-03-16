import React from "react";
import { Card } from "../shared/Card";
import { PriceBreakdown } from "./PriceBreakdown";
import type { NegotiationOutcomeResponse } from "../../api/types";

export function OutcomeDisplay({
  outcome,
}: {
  outcome: NegotiationOutcomeResponse;
}) {
  const isAgreement = outcome.outcome === "agreement";
  const isNoDeal = outcome.outcome === "no_deal";

  return (
    <Card
      className={`border-2 transition-all duration-500 ${
        isAgreement
          ? "border-green-200 bg-green-50/30"
          : isNoDeal
            ? "border-gray-200"
            : "border-red-200 bg-red-50/30"
      }`}
    >
      <div className="mb-4">
        <h3 className="text-lg font-semibold">
          {isAgreement
            ? "Deal Reached"
            : isNoDeal
              ? "No Deal"
              : "Negotiation Error"}
        </h3>
        <p className="text-sm text-gray-500 mt-1">
          {isAgreement
            ? "The AI agents successfully negotiated a price within the TEE."
            : isNoDeal
              ? "The negotiation did not result in a deal — the constraints could not be satisfied."
              : "An error occurred during the negotiation process."}
        </p>
      </div>

      {isAgreement && outcome.final_price !== null && (
        <PriceBreakdown
          finalPrice={outcome.final_price}
          reason={outcome.reason}
          rounds={outcome.negotiation_rounds}
        />
      )}

      {/* human-requested: show reason text for all outcomes */}
      {!isAgreement && outcome.reason && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg text-sm text-gray-600">
          {outcome.reason}
        </div>
      )}
    </Card>
  );
}
