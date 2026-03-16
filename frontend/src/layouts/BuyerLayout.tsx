import React from "react";
import { AppShell } from "../components/shared/AppShell";
import { ProtectedRoute } from "../routes/ProtectedRoute";

export function BuyerLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="buyer">
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}
