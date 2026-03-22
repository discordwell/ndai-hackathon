import React from "react";
import { AuthProvider } from "./contexts/AuthContext";
import { WalletProvider } from "./contexts/WalletContext";
import { Router } from "./routes";

export function App() {
  return (
    <AuthProvider>
      <WalletProvider>
        <Router />
      </WalletProvider>
    </AuthProvider>
  );
}
