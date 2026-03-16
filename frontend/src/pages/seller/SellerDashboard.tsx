import React from "react";
import { Card } from "../../components/shared/Card";
import { useInventions } from "../../hooks/useInventions";
import { useAgreements } from "../../hooks/useAgreements";

export function SellerDashboard() {
  const { inventions } = useInventions();
  const { agreements } = useAgreements();
  const activeInventions = inventions.filter((i) => i.status === "active");
  const completedDeals = agreements.filter((a) =>
    a.status.startsWith("completed_")
  );

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Inventor Dashboard</h1>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <Card>
          <div className="text-3xl font-bold text-ndai-600">
            {activeInventions.length}
          </div>
          <div className="text-sm text-gray-500 mt-1">Active Inventions</div>
        </Card>
        <Card>
          <div className="text-3xl font-bold text-ndai-600">
            {agreements.length}
          </div>
          <div className="text-sm text-gray-500 mt-1">Agreements</div>
        </Card>
        <Card>
          <div className="text-3xl font-bold text-ndai-600">
            {completedDeals.length}
          </div>
          <div className="text-sm text-gray-500 mt-1">Completed Deals</div>
        </Card>
      </div>
      <div className="flex gap-4">
        <a
          href="#/seller/inventions/new"
          className="inline-flex px-4 py-2 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 font-medium text-sm"
        >
          Submit New Invention
        </a>
        <a
          href="#/seller/inventions"
          className="inline-flex px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm"
        >
          View All Inventions
        </a>
      </div>
    </div>
  );
}
