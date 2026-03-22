import React from "react";
import { ProtectedRoute } from "../routes/ProtectedRoute";
import { AppShell } from "../components/shared/AppShell";

export function VulnLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}
