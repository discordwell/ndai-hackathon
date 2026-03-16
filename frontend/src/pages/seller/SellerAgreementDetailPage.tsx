import React, { useState, useEffect } from "react";
import { getAgreement } from "../../api/agreements";
import { getNegotiationOutcome } from "../../api/negotiations";
import { Card } from "../../components/shared/Card";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { StatusBadge } from "../../components/shared/StatusBadge";
import { OutcomeDisplay } from "../../components/negotiation/OutcomeDisplay";
import type { AgreementResponse, NegotiationOutcomeResponse } from "../../api/types";

export function SellerAgreementDetailPage({ id }: { id: string }) {
  const [agreement, setAgreement] = useState<AgreementResponse | null>(null);
  const [outcome, setOutcome] = useState<NegotiationOutcomeResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const a = await getAgreement(id);
        setAgreement(a);
        if (a.status.startsWith("completed_")) {
          const o = await getNegotiationOutcome(id);
          setOutcome(o);
        }
      } catch {
        // handled by null state
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) return <LoadingSpinner />;
  if (!agreement) return <div className="text-red-600">Agreement not found</div>;

  return (
    <div className="max-w-2xl">
      <a
        href="#/seller/agreements"
        className="text-sm text-ndai-600 hover:text-ndai-700 mb-4 inline-block"
      >
        &larr; Back to agreements
      </a>
      <h1 className="text-2xl font-bold mb-6">Agreement Detail</h1>

      <Card className="mb-6">
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Status</span>
            <div className="mt-1">
              <StatusBadge status={agreement.status} />
            </div>
          </div>
          <div>
            <span className="text-gray-500">Invention</span>
            <div className="mt-1 font-mono text-xs">{agreement.invention_id.slice(0, 12)}...</div>
          </div>
          <div>
            <span className="text-gray-500">Budget Cap</span>
            <div className="mt-1 font-medium">
              {agreement.budget_cap?.toFixed(2) ?? "—"}
            </div>
          </div>
          <div>
            <span className="text-gray-500">Theta</span>
            <div className="mt-1 font-medium">
              {agreement.theta?.toFixed(3) ?? "—"}
            </div>
          </div>
          <div>
            <span className="text-gray-500">Alpha-0</span>
            <div className="mt-1 font-medium">
              {agreement.alpha_0?.toFixed(2) ?? "—"}
            </div>
          </div>
        </div>
      </Card>

      {outcome && <OutcomeDisplay outcome={outcome} />}
    </div>
  );
}
