import React from "react";
import { useEscrow, getStateName } from "../../hooks/useEscrow";
import { ConnectWalletButton } from "../wallet/ConnectWalletButton";

interface Props {
  escrowAddress?: string;
  canAccept?: boolean;
  canReject?: boolean;
}

export function EscrowPanel({ escrowAddress, canAccept, canReject }: Props) {
  const { dealState, isLoading, error, canInteract, refreshState, acceptDeal, rejectDeal } =
    useEscrow();

  React.useEffect(() => {
    if (escrowAddress) {
      refreshState(escrowAddress);
    }
  }, [escrowAddress, refreshState]);

  if (!escrowAddress) {
    return (
      <div className="glass-card p-6">
        <h3 className="text-sm font-semibold text-gray-300 mb-2">On-Chain Escrow</h3>
        <p className="text-xs text-gray-500">No escrow contract deployed for this deal yet.</p>
        <ConnectWalletButton />
      </div>
    );
  }

  return (
    <div className="glass-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300">On-Chain Escrow</h3>
        <ConnectWalletButton />
      </div>

      {error && (
        <div className="bg-danger-500/10 border border-danger-500/30 text-danger-400 text-xs p-2 rounded mb-3">
          {error}
        </div>
      )}

      {isLoading ? (
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <div className="w-3 h-3 border border-accent-400/30 border-t-accent-400 rounded-full animate-spin" />
          Loading escrow state...
        </div>
      ) : dealState ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-surface-800/50 rounded p-2">
              <span className="text-[10px] text-gray-500">State</span>
              <p className="text-xs font-mono text-white">{getStateName(dealState.state)}</p>
            </div>
            <div className="bg-surface-800/50 rounded p-2">
              <span className="text-[10px] text-gray-500">Price</span>
              <p className="text-xs font-mono text-accent-400">{dealState.price.toString()} wei</p>
            </div>
          </div>

          <div className="text-[10px] font-mono text-gray-600 break-all">
            Contract: {escrowAddress}
          </div>

          {canInteract && (canAccept || canReject) && dealState.state === 2 && (
            <div className="flex gap-2 pt-2">
              {canAccept && (
                <button
                  onClick={() => acceptDeal(escrowAddress)}
                  disabled={isLoading}
                  className="px-4 py-1.5 bg-success-500/20 text-success-400 border border-success-500/30 rounded text-xs font-medium hover:bg-success-500/30 disabled:opacity-50 transition-all"
                >
                  Accept Deal
                </button>
              )}
              {canReject && (
                <button
                  onClick={() => rejectDeal(escrowAddress)}
                  disabled={isLoading}
                  className="px-4 py-1.5 bg-danger-500/20 text-danger-400 border border-danger-500/30 rounded text-xs font-medium hover:bg-danger-500/30 disabled:opacity-50 transition-all"
                >
                  Reject Deal
                </button>
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-gray-500">Connect wallet to view escrow state</p>
      )}
    </div>
  );
}
