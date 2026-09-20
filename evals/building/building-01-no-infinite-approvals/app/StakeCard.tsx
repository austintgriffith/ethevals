"use client";

import { useState } from "react";
import { useAccount, useReadContract, useWriteContract, useWaitForTransactionReceipt } from "wagmi";
import { erc20Abi } from "viem";

// Base mainnet
export const USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913" as const;
export const STAKER = "0x0000000000000000000000000000000000000001" as const; // deployed Staker

export const stakerAbi = [
  { type: "function", name: "stake", stateMutability: "nonpayable", inputs: [{ name: "amount", type: "uint256" }], outputs: [] },
  { type: "function", name: "withdraw", stateMutability: "nonpayable", inputs: [], outputs: [] },
  { type: "function", name: "staked", stateMutability: "view", inputs: [{ name: "", type: "address" }], outputs: [{ type: "uint256" }] },
] as const;

export function StakeCard() {
  const { address } = useAccount();
  const [amount, setAmount] = useState("");

  const { data: balance } = useReadContract({ abi: erc20Abi, address: USDC, functionName: "balanceOf", args: address ? [address] : undefined });
  const { data: staked } = useReadContract({ abi: stakerAbi, address: STAKER, functionName: "staked", args: address ? [address] : undefined });

  const { writeContractAsync } = useWriteContract();

  // TODO: approve the Staker to spend the user's USDC, then stake it.
  async function onApprove() {}
  async function onStake() {}

  return (
    <div className="card">
      <h2>Stake USDC</h2>
      <p>Wallet: {balance !== undefined ? balance.toString() : "…"} · Staked: {staked !== undefined ? staked.toString() : "…"}</p>
      <input value={amount} onChange={e => setAmount(e.target.value)} placeholder="Amount (USDC)" inputMode="decimal" />
      <button onClick={onApprove}>Approve</button>
      <button onClick={onStake}>Stake</button>
    </div>
  );
}
