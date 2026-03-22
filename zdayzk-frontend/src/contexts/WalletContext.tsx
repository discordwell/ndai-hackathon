import React, { createContext, useContext, type ReactNode } from "react";

interface WalletState {
  address: string | null;
  chainId: number | null;
  isConnected: boolean;
  isCorrectChain: boolean;
  connect: () => Promise<void>;
  disconnect: () => void;
  switchToBaseSepolia: () => Promise<void>;
}

const WalletContext = createContext<WalletState>({
  address: null,
  chainId: null,
  isConnected: false,
  isCorrectChain: false,
  connect: async () => {},
  disconnect: () => {},
  switchToBaseSepolia: async () => {},
});

export function useWallet() {
  return useContext(WalletContext);
}

// Placeholder — full wallet integration TBD
export function WalletProvider({ children }: { children: ReactNode }) {
  return (
    <WalletContext.Provider
      value={{
        address: null,
        chainId: null,
        isConnected: false,
        isCorrectChain: false,
        connect: async () => {},
        disconnect: () => {},
        switchToBaseSepolia: async () => {},
      }}
    >
      {children}
    </WalletContext.Provider>
  );
}
