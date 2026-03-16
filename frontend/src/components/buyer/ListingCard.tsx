import React from "react";
import { Card } from "../shared/Card";
import type { ListingResponse } from "../../api/types";

interface Props {
  listing: ListingResponse;
  onSelect: (id: string) => void;
}

export function ListingCard({ listing, onSelect }: Props) {
  return (
    <Card onClick={() => onSelect(listing.id)}>
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">{listing.title}</h3>
          {listing.anonymized_summary && (
            <p className="text-sm text-gray-500 mt-1 line-clamp-2">
              {listing.anonymized_summary}
            </p>
          )}
          <div className="flex gap-2 mt-3">
            {listing.category && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                {listing.category}
              </span>
            )}
            <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
              {listing.development_stage}
            </span>
          </div>
        </div>
      </div>
    </Card>
  );
}
