import React, { useState, useEffect } from "react";
import { LoadingSpinner } from "../../components/shared/LoadingSpinner";
import { EmptyState } from "../../components/shared/EmptyState";
import { listVulns, type VulnResponse } from "../../api/vulns";

export function VulnListPage() {
  const [vulns, setVulns] = useState<VulnResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    listVulns()
      .then(setVulns)
      .catch((e) => setError(e.detail || "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">My Vulnerabilities</h1>
        <a
          href="#/vuln/submit"
          className="px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 text-sm font-medium"
        >
          Submit New
        </a>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-red-600">{error}</div>
      ) : vulns.length === 0 ? (
        <EmptyState
          title="No vulnerabilities submitted"
          description="Submit your first vulnerability to start selling"
        />
      ) : (
        <div className="space-y-3">
          {vulns.map((v) => (
            <div
              key={v.id}
              className="bg-white rounded-xl border border-gray-100 p-4 flex items-center justify-between"
            >
              <div>
                <h3 className="font-medium">
                  {v.target_software} {v.target_version}
                </h3>
                <p className="text-sm text-gray-500">
                  {v.vulnerability_class} &middot; {v.impact_type} &middot; CVSS {v.cvss_self_assessed.toFixed(1)}
                </p>
              </div>
              <span
                className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                  v.status === "active"
                    ? "bg-green-100 text-green-800"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {v.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
