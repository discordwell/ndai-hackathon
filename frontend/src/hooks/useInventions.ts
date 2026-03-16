import { useState, useEffect, useCallback } from "react";
import { listInventions } from "../api/inventions";
import type { InventionResponse } from "../api/types";

export function useInventions() {
  const [inventions, setInventions] = useState<InventionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listInventions();
      setInventions(data);
      setError(null);
    } catch (err: any) {
      setError(err.detail || "Failed to load inventions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { inventions, loading, error, refresh };
}
