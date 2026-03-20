import React from "react";
import { AppShell } from "../components/shared/AppShell";
import { ProtectedRoute } from "../routes/ProtectedRoute";

export function RecallLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}
