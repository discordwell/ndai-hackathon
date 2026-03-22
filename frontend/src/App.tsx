import React from "react";
import { AuthProvider } from "./contexts/AuthContext";
import { ZKAuthProvider } from "./contexts/ZKAuthContext";
import { Router } from "./routes";

export function App() {
  return (
    <AuthProvider>
      <ZKAuthProvider>
        <Router />
      </ZKAuthProvider>
    </AuthProvider>
  );
}
