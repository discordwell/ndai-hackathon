import React from "react";
import { ProtectedRoute } from "../routes/ProtectedRoute";
import { FeatureNav } from "../components/shared/FeatureNav";

export function PokerTableLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <div className="min-h-screen bg-gray-950 flex flex-col">
        <FeatureNav />
        <main className="flex-1">{children}</main>
      </div>
    </ProtectedRoute>
  );
}
