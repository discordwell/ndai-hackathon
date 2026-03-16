import { useState, useEffect, useCallback } from "react";
import { listAgreements } from "../api/agreements";
import type { AgreementResponse } from "../api/types";

export function useAgreements() {
  const [agreements, setAgreements] = useState<AgreementResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listAgreements();
      setAgreements(data);
      setError(null);
    } catch (err: any) {
      setError(err.detail || "Failed to load agreements");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { agreements, loading, error, refresh };
}
