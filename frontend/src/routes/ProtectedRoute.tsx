import React from "react";
import { useAuth } from "../contexts/AuthContext";

interface Props {
  role?: string;
  children: React.ReactNode;
}

export function ProtectedRoute({ role, children }: Props) {
  const { isAuthenticated, role: userRole } = useAuth();

  if (!isAuthenticated) {
    // Redirect to login
    window.location.hash = "#/login";
    return null;
  }

  if (role && userRole !== role) {
    // Wrong role — redirect to their dashboard
    window.location.hash = userRole === "seller" ? "#/seller" : "#/buyer";
    return null;
  }

  return <>{children}</>;
}
