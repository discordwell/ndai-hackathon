import { useState, useEffect, useCallback } from "react";
import { listPublicListings } from "../api/inventions";
import type { ListingResponse } from "../api/types";

export function useListings() {
  const [listings, setListings] = useState<ListingResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPublicListings();
      setListings(data);
      setError(null);
    } catch (err: any) {
      setError(err.detail || "Failed to load listings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { listings, loading, error, refresh };
}
