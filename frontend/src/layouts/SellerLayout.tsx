import React from "react";
import { AppShell } from "../components/shared/AppShell";
import { ProtectedRoute } from "../routes/ProtectedRoute";

export function SellerLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute role="seller">
      <AppShell>{children}</AppShell>
    </ProtectedRoute>
  );
}
