import React from "react";
import { AuthProvider } from "./contexts/AuthContext";
import { ZKAuthProvider } from "./contexts/ZKAuthContext";
import { ToastProvider } from "./contexts/ToastContext";
import { Router } from "./routes";

export function App() {
  return (
    <AuthProvider>
      <ZKAuthProvider>
        <ToastProvider>
          <Router />
        </ToastProvider>
      </ZKAuthProvider>
    </AuthProvider>
  );
}
