import { useState, useCallback } from "react";
import { useWallet } from "../contexts/WalletContext";

// Minimal ABI for VulnEscrow interactions
const VULN_ESCROW_ABI = [
  "function state() view returns (uint8)",
  "function seller() view returns (address)",
  "function buyer() view returns (address)",
  "function price() view returns (uint256)",
  "function deadline() view returns (uint256)",
  "function deliveryHash() view returns (bytes32)",
  "function keyCommitment() view returns (bytes32)",
  "function acceptDeal()",
  "function rejectDeal()",
  "function claimExpired()",
  "event DealAccepted(address indexed seller, uint256 amount)",
  "event DealRejected(address indexed buyer, uint256 refundAmount)",
];

const VULN_ESCROW_FACTORY_ABI = [
  "function createEscrow(address _seller, address _operator, uint256 _price, uint256 _deadline, bool _isExclusive) payable returns (address)",
  "event EscrowCreated(address indexed escrow, address indexed buyer, address indexed seller)",
];

export interface EscrowDealInfo {
  state: number;
  seller: string;
  buyer: string;
  price: bigint;
  deadline: number;
  deliveryHash: string;
  keyCommitment: string;
}

const STATE_NAMES = ["Created", "Funded", "Verified", "Accepted", "Rejected", "Expired", "PatchRefunded"];

export function getStateName(state: number): string {
  return STATE_NAMES[state] ?? "Unknown";
}

export function useEscrow() {
  const { address, isConnected, isCorrectChain } = useWallet();
  const [dealState, setDealState] = useState<EscrowDealInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getEthers = useCallback(async () => {
    const { ethers } = await import("ethers");
    const eth = (window as any).ethereum;
    if (!eth) throw new Error("No wallet connected");
    const provider = new ethers.BrowserProvider(eth);
    const signer = await provider.getSigner();
    return { ethers, provider, signer };
  }, []);

  const refreshState = useCallback(async (escrowAddr: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const { ethers, provider } = await getEthers();
      const contract = new ethers.Contract(escrowAddr, VULN_ESCROW_ABI, provider);
      const [state, seller, buyer, price, deadline, deliveryHash, keyCommitment] =
        await Promise.all([
          contract.state(),
          contract.seller(),
          contract.buyer(),
          contract.price(),
          contract.deadline(),
          contract.deliveryHash(),
          contract.keyCommitment(),
        ]);
      setDealState({
        state: Number(state),
        seller,
        buyer,
        price,
        deadline: Number(deadline),
        deliveryHash,
        keyCommitment,
      });
    } catch (err: any) {
      setError(err.message || "Failed to read escrow state");
    } finally {
      setIsLoading(false);
    }
  }, [getEthers]);

  const fundEscrow = useCallback(
    async (
      factoryAddr: string,
      seller: string,
      operator: string,
      price: bigint,
      deadline: number,
      isExclusive: boolean
    ): Promise<string> => {
      if (!isConnected || !isCorrectChain) throw new Error("Wallet not connected to Base Sepolia");
      setIsLoading(true);
      setError(null);
      try {
        const { ethers, signer } = await getEthers();
        const factory = new ethers.Contract(factoryAddr, VULN_ESCROW_FACTORY_ABI, signer);
        const tx = await factory.createEscrow(seller, operator, price, deadline, isExclusive, {
          value: price,
        });
        const receipt = await tx.wait();
        const event = receipt.logs.find(
          (log: any) => log.fragment?.name === "EscrowCreated"
        );
        return event?.args?.[0] ?? "";
      } catch (err: any) {
        setError(err.message || "Failed to fund escrow");
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [isConnected, isCorrectChain, getEthers]
  );

  const acceptDeal = useCallback(
    async (escrowAddr: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const { ethers, signer } = await getEthers();
        const contract = new ethers.Contract(escrowAddr, VULN_ESCROW_ABI, signer);
        const tx = await contract.acceptDeal();
        await tx.wait();
        await refreshState(escrowAddr);
      } catch (err: any) {
        setError(err.message || "Failed to accept deal");
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [getEthers, refreshState]
  );

  const rejectDeal = useCallback(
    async (escrowAddr: string) => {
      setIsLoading(true);
      setError(null);
      try {
        const { ethers, signer } = await getEthers();
        const contract = new ethers.Contract(escrowAddr, VULN_ESCROW_ABI, signer);
        const tx = await contract.rejectDeal();
        await tx.wait();
        await refreshState(escrowAddr);
      } catch (err: any) {
        setError(err.message || "Failed to reject deal");
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [getEthers, refreshState]
  );

  return {
    dealState,
    isLoading,
    error,
    canInteract: isConnected && isCorrectChain,
    refreshState,
    fundEscrow,
    acceptDeal,
    rejectDeal,
  };
}
