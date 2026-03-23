import React from "react";
import { Card } from "../shared/Card";
import type { ListingResponse } from "../../api/types";

interface Props {
  listing: ListingResponse;
  selected?: boolean;
  onSelect: (id: string) => void;
}

const STAGES = ["concept", "prototype", "tested", "production"];

function StageDots({ stage }: { stage: string }) {
  const idx = STAGES.indexOf(stage.toLowerCase());
  const level = idx >= 0 ? idx + 1 : 1;
  return (
    <div className="flex items-center gap-1" title={stage}>
      {STAGES.map((_, i) => (
        <div
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${
            i < level ? "bg-ndai-500" : "bg-gray-200"
          }`}
        />
      ))}
      <span className="text-xs text-gray-500 ml-1 capitalize">{stage}</span>
    </div>
  );
}

export function ListingCard({ listing, selected, onSelect }: Props) {
  return (
    <Card
      onClick={() => onSelect(listing.id)}
      className={`transition-all cursor-pointer ${
        selected ? "ring-2 ring-ndai-500 border-ndai-200" : "hover:border-ndai-200"
      }`}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <h3 className="font-semibold text-gray-900">{listing.title}</h3>
          {listing.anonymized_summary && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">
              {listing.anonymized_summary}
            </p>
          )}
          <div className="flex items-center gap-3 mt-3">
            {listing.category && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                {listing.category}
              </span>
            )}
            <StageDots stage={listing.development_stage} />
          </div>
        </div>
      </div>
    </Card>
  );
}
