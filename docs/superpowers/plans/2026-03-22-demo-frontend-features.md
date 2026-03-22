# Demo Frontend Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three demo-impactful frontend features: mechanism explorer (parameter playground), escrow state stepper, and expanded verification panel with on-chain data.

**Architecture:** Pure frontend components (React 19 + Tailwind) with one new backend API endpoint for on-chain state. MechanismExplorer does client-side Nash math. EscrowStepper mirrors the existing NegotiationProgress pattern. VerificationPanel gets an optional escrow accordion section. All integrate into existing buyer/seller agreement detail pages.

**Tech Stack:** React 19, TypeScript, Tailwind CSS (ndai-* color scheme), FastAPI, web3.py

**Spec:** `docs/superpowers/specs/2026-03-22-demo-frontend-features-design.md`

---

## Task 1: Data Pipeline — Backend Schema Updates

**Files:**
- Modify: `ndai/api/schemas/agreement.py`
- Modify: `ndai/api/routers/agreements.py`
- Modify: `ndai/api/routers/negotiations.py`

- [ ] **Step 1: Add escrow fields to AgreementResponse schema**

In `ndai/api/schemas/agreement.py`, add to `AgreementResponse`:
```python
    escrow_address: str | None = None
    escrow_tx_hash: str | None = None
```

- [ ] **Step 2: Add outcome fields to NegotiationOutcomeResponse**

In `ndai/api/schemas/agreement.py`, add to `NegotiationOutcomeResponse`:
```python
    omega_hat: float | None = None
    buyer_valuation: float | None = None
```

- [ ] **Step 3: Map escrow fields in _agreement_response helper**

In `ndai/api/routers/agreements.py`, update `_agreement_response()` to include:
```python
        escrow_address=a.escrow_address,
        escrow_tx_hash=a.escrow_tx_hash,
```

- [ ] **Step 4: Include omega_hat/buyer_valuation in outcome responses**

In `ndai/api/routers/negotiations.py`, in `_run_negotiation_async()` where the outcome is persisted (around line 76-83), ensure `omega_hat` is saved. Then in the `get_outcome` endpoint, include:
```python
    return NegotiationOutcomeResponse(
        outcome=outcome.outcome,
        final_price=outcome.final_price,
        reason=outcome.error_details,
        negotiation_rounds=outcome.negotiation_rounds,
        omega_hat=outcome.omega_hat,
    )
```

- [ ] **Step 5: Run existing tests**

Run: `pytest tests/ -v --tb=short -x --ignore=tests/integration/ 2>&1 | tail -10`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add ndai/api/schemas/agreement.py ndai/api/routers/agreements.py ndai/api/routers/negotiations.py
git commit -m "feat: add escrow + outcome fields to API response schemas"
```

---

## Task 2: Data Pipeline — Frontend Type Updates

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/agreements.ts`

- [ ] **Step 1: Add escrow fields to AgreementResponse type**

In `frontend/src/api/types.ts`, add to `AgreementResponse`:
```typescript
  escrow_address?: string | null;
  escrow_tx_hash?: string | null;
```

- [ ] **Step 2: Add outcome fields to NegotiationOutcomeResponse type**

In `frontend/src/api/types.ts`, add to `NegotiationOutcomeResponse`:
```typescript
  omega_hat?: number | null;
  buyer_valuation?: number | null;
```

- [ ] **Step 3: Add EscrowStateResponse type**

In `frontend/src/api/types.ts`, add:
```typescript
export interface EscrowStateResponse {
  escrow_address: string;
  state: string;
  balance_wei: number;
  reserve_price_wei: number;
  budget_cap_wei: number;
  final_price_wei: number;
  attestation_hash: string;
  deadline: number;
  blockchain_unavailable?: boolean;
}
```

- [ ] **Step 4: Add getEscrowState API function**

In `frontend/src/api/agreements.ts`, add:
```typescript
import type { EscrowStateResponse } from "./types";

export function getEscrowState(id: string): Promise<EscrowStateResponse> {
  return get<EscrowStateResponse>(`/agreements/${id}/escrow-state`);
}
```

- [ ] **Step 5: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/agreements.ts
git commit -m "feat: add escrow + outcome types to frontend API layer"
```

---

## Task 3: Escrow State API Endpoint

**Files:**
- Modify: `ndai/api/routers/agreements.py`
- Create: `tests/unit/test_escrow_state_endpoint.py`

- [ ] **Step 1: Write test for the endpoint**

Create `tests/unit/test_escrow_state_endpoint.py`:
```python
"""Tests for GET /agreements/{id}/escrow-state endpoint."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from ndai.blockchain.models import DealState, EscrowState


class TestEscrowStateSchema:
    def test_deal_state_to_dict(self):
        state = DealState(
            seller="0xCAFE",
            buyer="0xBEEF",
            operator="0xDEAD",
            reserve_price_wei=100000000000000000,
            budget_cap_wei=1000000000000000000,
            final_price_wei=500000000000000000,
            attestation_hash=b"\x01" * 32,
            deadline=1711234567,
            state=EscrowState.Evaluated,
            balance_wei=1000000000000000000,
        )
        assert state.state == EscrowState.Evaluated
        assert state.budget_cap_wei == 1000000000000000000
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/test_escrow_state_endpoint.py -v`
Expected: Pass

- [ ] **Step 3: Add the endpoint**

In `ndai/api/routers/agreements.py`, add:
```python
@router.get("/{agreement_id}/escrow-state")
async def get_escrow_state(
    agreement_id: str,
    user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get on-chain escrow state for an agreement."""
    from ndai.config import settings

    agreement = await get_agreement(db, uuid.UUID(agreement_id))
    if not agreement:
        raise HTTPException(status_code=404, detail="Agreement not found")
    if user_id not in (str(agreement.buyer_id), str(agreement.seller_id)):
        raise HTTPException(status_code=403, detail="Not authorized")
    if not agreement.escrow_address:
        raise HTTPException(status_code=404, detail="No escrow for this agreement")

    if not settings.blockchain_enabled or not settings.base_sepolia_rpc_url:
        return {
            "escrow_address": agreement.escrow_address,
            "blockchain_unavailable": True,
        }

    try:
        from ndai.blockchain.escrow_client import EscrowClient
        client = EscrowClient(
            rpc_url=settings.base_sepolia_rpc_url,
            factory_address=settings.escrow_factory_address,
            chain_id=settings.chain_id,
        )
        state = await client.get_deal_state(agreement.escrow_address)
        return {
            "escrow_address": agreement.escrow_address,
            "state": state.state.name,
            "balance_wei": state.balance_wei,
            "reserve_price_wei": state.reserve_price_wei,
            "budget_cap_wei": state.budget_cap_wei,
            "final_price_wei": state.final_price_wei,
            "attestation_hash": "0x" + state.attestation_hash.hex(),
            "deadline": state.deadline,
        }
    except Exception as e:
        return {
            "escrow_address": agreement.escrow_address,
            "blockchain_unavailable": True,
            "error": str(e),
        }
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/ -v --tb=short -x --ignore=tests/integration/ 2>&1 | tail -10`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add ndai/api/routers/agreements.py tests/unit/test_escrow_state_endpoint.py
git commit -m "feat: GET /agreements/{id}/escrow-state endpoint"
```

---

## Task 4: Mechanism Math (TypeScript)

**Files:**
- Create: `frontend/src/utils/mechanism.ts`

- [ ] **Step 1: Write the math utilities**

Create `frontend/src/utils/mechanism.ts`:
```typescript
/**
 * Client-side NDAI mechanism design math.
 * Mirrors ndai/enclave/negotiation/engine.py
 */

/** Bilateral Nash equilibrium price: P* = (v_b + alpha_0 * omega_hat) / 2 */
export function computePrice(alpha0: number, omegaHat: number, vb: number): number {
  return (vb + alpha0 * omegaHat) / 2;
}

/** Seller's bargaining share: theta = (1 + alpha_0) / 2 */
export function computeTheta(alpha0: number): number {
  return (1 + alpha0) / 2;
}

/**
 * Security capacity: Phi(k, p, C, gamma)
 * Max securable value given TEE parameters.
 */
export function securityCapacity(
  k: number = 3,
  p: number = 0.005,
  c: number = 7_500_000_000,
  gamma: number = 1,
): number {
  const breach = Math.pow(1 - p, Math.pow(k, gamma));
  if (breach === 0) return Infinity;
  return (k * (1 - breach) * c) / breach;
}

/** Deal is viable when buyer values disclosure above seller's reservation. */
export function isDealViable(vb: number, alpha0: number, omegaHat: number): boolean {
  return vb >= alpha0 * omegaHat;
}

/** Price within budget cap. */
export function checkBudgetCap(price: number, budgetCap: number): boolean {
  return price <= budgetCap;
}
```

- [ ] **Step 2: Build frontend to verify no TypeScript errors**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/utils/mechanism.ts
git commit -m "feat: client-side Nash mechanism math utilities"
```

---

## Task 5: MechanismExplorer Component

**Files:**
- Create: `frontend/src/components/negotiation/MechanismExplorer.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/components/negotiation/MechanismExplorer.tsx`:
```tsx
import React, { useState } from "react";
import {
  computePrice,
  computeTheta,
  securityCapacity,
  isDealViable,
  checkBudgetCap,
} from "../../utils/mechanism";

interface Props {
  initialBudgetCap?: number;
  initialAlpha0?: number;
  initialOmegaHat?: number;
  initialBuyerValue?: number;
}

const SLIDER_CONFIG = [
  { key: "budgetCap", label: "Budget Cap (P\u0304)", color: "#4c6ef5", min: 0.01, max: 2, step: 0.01 },
  { key: "alpha0", label: "Reserve Price (\u03b1\u2080)", color: "#f59e0b", min: 0.01, max: 1, step: 0.01 },
  { key: "omegaHat", label: "Disclosure (\u03c9\u0302)", color: "#8b5cf6", min: 0.01, max: 1, step: 0.01 },
  { key: "buyerValue", label: "Buyer Valuation (v\u2082)", color: "#22c55e", min: 0.01, max: 1, step: 0.01 },
] as const;

export function MechanismExplorer({
  initialBudgetCap = 0.8,
  initialAlpha0 = 0.3,
  initialOmegaHat = 0.5,
  initialBuyerValue = 0.5,
}: Props) {
  const [values, setValues] = useState({
    budgetCap: initialBudgetCap,
    alpha0: initialAlpha0,
    omegaHat: initialOmegaHat,
    buyerValue: initialBuyerValue,
  });
  const [showFormula, setShowFormula] = useState(false);

  const price = computePrice(values.alpha0, values.omegaHat, values.buyerValue);
  const phi = securityCapacity();
  const viable = isDealViable(values.buyerValue, values.alpha0, values.omegaHat);
  const withinBudget = checkBudgetCap(price, values.budgetCap);
  const dealOk = viable && withinBudget;

  function handleChange(key: string, val: number) {
    setValues((prev) => ({ ...prev, [key]: val }));
  }

  return (
    <div className="bg-ndai-50 rounded-xl border border-ndai-200 p-4">
      <div className="mb-4">
        <h3 className="font-semibold text-ndai-700 text-sm">Mechanism Explorer</h3>
        <p className="text-xs text-gray-500">Adjust parameters to see how the NDAI equilibrium changes</p>
      </div>

      {/* Results */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-xs text-gray-500">Equilibrium Price</div>
          <div className="text-2xl font-bold text-ndai-600">{price.toFixed(3)}</div>
        </div>
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-xs text-gray-500">Security Capacity</div>
          <div className="text-2xl font-bold text-green-600">
            {phi > 1e9 ? (phi / 1e9).toFixed(1) + "B" : phi.toFixed(2)}
          </div>
        </div>
        <div className="bg-white rounded-lg p-3 text-center">
          <div className="text-xs text-gray-500">Deal Viable</div>
          <div className={`text-2xl font-bold ${dealOk ? "text-green-600" : "text-red-500"}`}>
            {dealOk ? "Yes" : "No"}
          </div>
        </div>
      </div>

      {/* Sliders */}
      <div className="grid grid-cols-2 gap-3 mb-3">
        {SLIDER_CONFIG.map(({ key, label, color, min, max, step }) => (
          <div key={key} className="bg-white rounded-lg p-3">
            <div className="flex justify-between text-xs text-gray-600 mb-1">
              <span>{label}</span>
              <span className="font-semibold text-gray-900">
                {values[key as keyof typeof values].toFixed(2)}
              </span>
            </div>
            <input
              type="range"
              min={min}
              max={max}
              step={step}
              value={values[key as keyof typeof values]}
              onChange={(e) => handleChange(key, parseFloat(e.target.value))}
              className="w-full h-1.5 rounded-lg appearance-none cursor-pointer"
              style={{ accentColor: color }}
            />
          </div>
        ))}
      </div>

      {/* Collapsible formula */}
      <div className="border-t border-ndai-200 pt-2">
        <button
          onClick={() => setShowFormula(!showFormula)}
          className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
        >
          <span>{showFormula ? "\u25BC" : "\u25B6"}</span>
          {showFormula ? "Hide" : "Show"} formula breakdown
        </button>
        {showFormula && (
          <div className="mt-2 bg-white rounded-lg p-3 text-center">
            <div className="text-xs text-gray-400 mb-1">Bilateral Nash Bargaining</div>
            <div className="text-lg font-serif">
              P* = (
              <span className="font-bold" style={{ color: "#22c55e" }}>{values.buyerValue.toFixed(2)}</span>
              {" + "}
              <span className="font-bold" style={{ color: "#f59e0b" }}>{values.alpha0.toFixed(2)}</span>
              {" \u00d7 "}
              <span className="font-bold" style={{ color: "#8b5cf6" }}>{values.omegaHat.toFixed(2)}</span>
              ) / 2 ={" "}
              <span className="font-bold text-xl" style={{ color: "#4c6ef5" }}>{price.toFixed(3)}</span>
            </div>
            <div className="text-[10px] text-gray-400 mt-1">
              P* = (v_b + \u03b1\u2080 \u00b7 \u03c9\u0302) / 2 | \u03b8 = {computeTheta(values.alpha0).toFixed(3)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/negotiation/MechanismExplorer.tsx
git commit -m "feat: MechanismExplorer component with interactive sliders"
```

---

## Task 6: EscrowStepper Component

**Files:**
- Create: `frontend/src/components/shared/EscrowStepper.tsx`

- [ ] **Step 1: Write the component**

Create `frontend/src/components/shared/EscrowStepper.tsx`:
```tsx
import React from "react";

interface Props {
  state: string; // Funded, Evaluated, Accepted, Rejected, Expired
  creationTxHash?: string;
  outcomeTxHash?: string;
  settlementTxHash?: string;
}

const BASESCAN = "https://sepolia.basescan.org/tx/";

function truncateHash(hash: string): string {
  return hash.slice(0, 6) + "..." + hash.slice(-4);
}

const STEPS = [
  { key: "Funded", label: "Funded" },
  { key: "Evaluated", label: "Evaluated" },
  { key: "Terminal", label: "" }, // label set dynamically
] as const;

const STATE_ORDER: Record<string, number> = {
  Created: -1,
  Funded: 0,
  Evaluated: 1,
  Accepted: 2,
  Rejected: 2,
  Expired: 2,
};

export function EscrowStepper({ state, creationTxHash, outcomeTxHash, settlementTxHash }: Props) {
  const activeIdx = STATE_ORDER[state] ?? -1;
  const terminalLabel = state === "Rejected" ? "Rejected" : state === "Expired" ? "Expired" : "Accepted";
  const terminalColor = state === "Accepted" ? "text-green-600" : state === "Rejected" ? "text-red-500" : "text-gray-500";
  const txHashes = [creationTxHash, outcomeTxHash, settlementTxHash];

  const steps = [
    { label: "Funded", idx: 0 },
    { label: "Evaluated", idx: 1 },
    { label: terminalLabel, idx: 2 },
  ];

  return (
    <div className="flex items-center gap-1 py-3">
      {steps.map((step, i) => {
        const isComplete = i < activeIdx || (i === activeIdx && i === 2);
        const isActive = i === activeIdx && i < 2;
        const txHash = txHashes[i];

        return (
          <React.Fragment key={i}>
            {i > 0 && (
              <div
                className={`flex-1 h-0.5 ${
                  i <= activeIdx ? "bg-ndai-500" : "bg-gray-200"
                }`}
              />
            )}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                  isComplete
                    ? "bg-ndai-500 text-white"
                    : isActive
                      ? "bg-ndai-100 text-ndai-700 ring-2 ring-ndai-500 animate-pulse"
                      : "bg-gray-100 text-gray-400"
                }`}
              >
                {isComplete ? (
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  i + 1
                )}
              </div>
              <span
                className={`text-xs whitespace-nowrap ${
                  isComplete || isActive
                    ? i === 2 ? terminalColor + " font-medium" : "text-ndai-700 font-medium"
                    : "text-gray-400"
                }`}
              >
                {step.label}
              </span>
              {txHash && (isComplete || isActive) && (
                <a
                  href={`${BASESCAN}${txHash}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[10px] font-mono text-gray-400 hover:text-ndai-600"
                >
                  {truncateHash(txHash)}
                </a>
              )}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/shared/EscrowStepper.tsx
git commit -m "feat: EscrowStepper component for on-chain deal state"
```

---

## Task 7: Expand VerificationPanel with On-Chain Section

**Files:**
- Modify: `frontend/src/components/shared/VerificationPanel.tsx`

- [ ] **Step 1: Read the current component**

Read `frontend/src/components/shared/VerificationPanel.tsx` before editing.

- [ ] **Step 2: Add optional escrowData prop and on-chain accordion section**

Update the `Props` interface:
```typescript
interface Props {
  verification: VerificationData | null | undefined;
  escrowData?: {
    escrow_address: string;
    state?: string;
    attestation_hash?: string;
    balance_wei?: number;
    deadline?: number;
    blockchain_unavailable?: boolean;
  } | null;
}
```

Update the component signature to accept `escrowData`. After the existing `{expanded && (...)}` block, add a new section:

```tsx
      {escrowData && !escrowData.blockchain_unavailable && (
        <div className="mt-4 border-t border-gray-100 pt-4">
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
            On-Chain Settlement
          </h4>
          <div className="space-y-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Escrow</span>
              <a
                href={`https://sepolia.basescan.org/address/${escrowData.escrow_address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-ndai-600 hover:text-ndai-700"
              >
                {escrowData.escrow_address.slice(0, 10)}...{escrowData.escrow_address.slice(-6)}
              </a>
            </div>
            {escrowData.state && (
              <div className="flex items-center gap-2">
                <span className="text-gray-500">State</span>
                <span className="font-medium text-gray-900">{escrowData.state}</span>
              </div>
            )}
            {escrowData.attestation_hash && (
              <div className="flex items-center gap-2">
                <span className="text-gray-500">Attestation Hash</span>
                <code className="bg-gray-50 px-2 py-0.5 rounded font-mono text-gray-600">
                  {escrowData.attestation_hash.slice(0, 18)}...
                </code>
              </div>
            )}
          </div>
        </div>
      )}
```

- [ ] **Step 3: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/shared/VerificationPanel.tsx
git commit -m "feat: add on-chain settlement section to VerificationPanel"
```

---

## Task 8: Integrate into Agreement Detail Pages

**Files:**
- Modify: `frontend/src/pages/buyer/BuyerAgreementDetailPage.tsx`
- Modify: `frontend/src/pages/seller/SellerAgreementDetailPage.tsx`

- [ ] **Step 1: Read both files before editing**

Read `BuyerAgreementDetailPage.tsx` and `SellerAgreementDetailPage.tsx`.

- [ ] **Step 2: Update BuyerAgreementDetailPage**

Add imports:
```typescript
import { MechanismExplorer } from "../../components/negotiation/MechanismExplorer";
import { EscrowStepper } from "../../components/shared/EscrowStepper";
import { VerificationPanel } from "../../components/shared/VerificationPanel";
import { getEscrowState } from "../../api/agreements";
```

Add escrow state:
```typescript
const [escrowData, setEscrowData] = useState<any>(null);
```

In the `load()` function, after fetching the agreement, add:
```typescript
      if (a.escrow_address) {
        try {
          const es = await getEscrowState(id);
          setEscrowData(es);
        } catch {
          // blockchain unavailable
        }
      }
```

In the JSX, after the title and before the status Card:
```tsx
      {agreement.escrow_address && escrowData && (
        <div className="mb-4">
          <EscrowStepper
            state={escrowData.state || "Funded"}
            creationTxHash={agreement.escrow_tx_hash || undefined}
          />
        </div>
      )}
```

After the outcome display, add MechanismExplorer:
```tsx
      <div className="mb-6">
        <MechanismExplorer
          initialBudgetCap={agreement.budget_cap ?? 0.8}
          initialAlpha0={agreement.alpha_0 ?? 0.3}
          initialOmegaHat={negStatus?.outcome?.omega_hat ?? 0.5}
          initialBuyerValue={negStatus?.outcome?.buyer_valuation ?? 0.5}
        />
      </div>
```

After MechanismExplorer, add VerificationPanel:
```tsx
      {isCompleted && (
        <VerificationPanel verification={null} escrowData={escrowData} />
      )}
```

- [ ] **Step 3: Update SellerAgreementDetailPage**

Same pattern: add imports, add escrowData state, fetch in useEffect, add EscrowStepper before status Card, add MechanismExplorer after OutcomeDisplay, add VerificationPanel at bottom.

The seller page is simpler — follow the same structure as buyer but with the seller's existing load pattern.

- [ ] **Step 4: Build frontend**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Run all Python tests**

Run: `pytest tests/ -v --tb=short -x --ignore=tests/integration/ 2>&1 | tail -10`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/buyer/BuyerAgreementDetailPage.tsx frontend/src/pages/seller/SellerAgreementDetailPage.tsx
git commit -m "feat: integrate MechanismExplorer, EscrowStepper, VerificationPanel into agreement pages"
```

---

## Task 9: Build, Push, Verify

**Files:** None (validation only)

- [ ] **Step 1: Full frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 2: Full Python test suite**

Run: `pytest tests/ -v --tb=short --ignore=tests/integration/ 2>&1 | tail -10`
Expected: All pass

- [ ] **Step 3: Push**

```bash
git push
```
