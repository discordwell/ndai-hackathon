# Demo Frontend Features Design

**Date:** 2026-03-22
**Status:** Approved
**Context:** Add three demo-impactful frontend features to the existing React + Tailwind UI: mechanism explorer, expanded verification panel, and escrow state stepper.

## Overview

Three components integrated into the existing buyer and seller agreement detail pages:

1. **Mechanism Explorer** — Interactive parameter playground with sliders for budget cap, reserve price, disclosure fraction, and buyer valuation. Computes Nash equilibrium price, security capacity, and deal viability in real-time. Client-side math only, no API calls. Collapsible formula breakdown.

2. **Verification Panel Expansion** — Extend the existing `VerificationPanel` component with an "On-Chain Settlement" accordion section showing escrow address, state, attestation hash, and tx hashes linked to BaseScan. Includes a "Verify Attestation" button that calls the contract's view function.

3. **Escrow State Stepper** — Horizontal step indicator (Funded → Evaluated → Accepted/Rejected/Expired) modeled after the existing `NegotiationProgress` component. Shows current state with pulsing animation, completed states with checkmarks, and truncated tx hash links under each step.

## 1. Mechanism Explorer

### Component: `MechanismExplorer.tsx`

**Location:** `frontend/src/components/negotiation/MechanismExplorer.tsx`

**Props:**
```typescript
interface MechanismExplorerProps {
  initialBudgetCap?: number;    // from agreement.budget_cap
  initialAlpha0?: number;       // from agreement.alpha_0 or invention.outside_option_value
  initialOmegaHat?: number;     // from outcome.omega_hat or invention.self_assessed_value
  initialBuyerValue?: number;   // from outcome.buyer_valuation or 0.5
}
```

**Behavior:**
- Four `<input type="range">` sliders in a 2x2 grid, all editable regardless of user role
- Three result cards at top: Equilibrium Price (P*), Security Capacity (Phi), Deal Viable (Yes/No)
- Results recalculate on every slider `onChange` event — no debounce needed (math is trivial)
- Collapsible formula section at bottom (collapsed by default), toggled by a "Show formula breakdown" link
- When expanded, shows: `P* = (v_b + alpha_0 * omega_hat) / 2` with color-coded variables matching slider colors, and the general form of the security capacity formula

**Slider config:**
| Slider | Label | Range | Step | Color |
|--------|-------|-------|------|-------|
| Budget Cap (P-bar) | Budget Cap | 0.01–2.0 | 0.01 | ndai-500 (#4c6ef5) |
| Reserve Price (alpha_0) | Reserve Price | 0.01–1.0 | 0.01 | amber-500 (#f59e0b) |
| Disclosure (omega_hat) | Disclosure Fraction | 0.01–1.0 | 0.01 | violet-500 (#8b5cf6) |
| Buyer Valuation (v_b) | Buyer Valuation | 0.01–1.0 | 0.01 | green-500 (#22c55e) |

**Math (client-side):** Reimplemented in TypeScript from `ndai/enclave/negotiation/engine.py`:
```typescript
// frontend/src/utils/mechanism.ts
function computePrice(alpha0: number, omegaHat: number, vb: number): number {
  return (vb + alpha0 * omegaHat) / 2;
}
function computeTheta(alpha0: number): number {
  return (1 + alpha0) / 2;
}
function securityCapacity(k: number, p: number, c: number, gamma: number): number {
  const breach = Math.pow(1 - p, Math.pow(k, gamma));
  return (k * (1 - breach) * c) / breach;
}
function isDealViable(vb: number, alpha0: number, omegaHat: number): boolean {
  return vb >= alpha0 * omegaHat;
}
function checkBudgetCap(price: number, budgetCap: number): boolean {
  return price <= budgetCap;
}
```

**Placement:** Below the existing agreement parameters section on both `BuyerAgreementDetailPage` and `SellerAgreementDetailPage`. Wrapped in a Card component. Always visible when agreement exists (no conditional on status).

### Styling

Follows existing patterns: `bg-ndai-50` background for the card, white sub-cards for results, `rounded-lg`, standard Tailwind spacing. Slider track styling via Tailwind's accent color utilities or inline styles for per-slider colors.

## 2. Verification Panel Expansion

### Changes to: `VerificationPanel.tsx`

**Location:** `frontend/src/components/shared/VerificationPanel.tsx`

**New accordion section: "On-Chain Settlement"**

Shows when `escrow_address` is present on the agreement:
- **Escrow Address** — Full address, linked to `https://sepolia.basescan.org/address/{address}`
- **Escrow State** — Current state as a StatusBadge (Funded=blue, Evaluated=yellow, Accepted=green, Rejected=red, Expired=gray)
- **Attestation Hash** — Hex string in monospace, truncated with copy button
- **Creation Tx** — Truncated hash linked to BaseScan tx page
- **Settlement Tx** — Truncated hash linked to BaseScan tx page (if exists)
- **Verify Attestation** button — Calls `GET /agreements/{id}/escrow-state` and displays the result (verified/not verified)

### New API Endpoint

**`GET /api/v1/agreements/{agreement_id}/escrow-state`**

Added to `ndai/api/routers/agreements.py`. Returns:
```json
{
  "escrow_address": "0x...",
  "state": "Evaluated",
  "balance_wei": 1000000000000000000,
  "reserve_price_wei": 100000000000000000,
  "budget_cap_wei": 1000000000000000000,
  "final_price_wei": 500000000000000000,
  "attestation_hash": "0x...",
  "deadline": 1711234567
}
```

Implementation: reads `agreement.escrow_address`, calls `EscrowClient.get_deal_state()`, returns the data. Falls back gracefully if blockchain is disabled or RPC is unreachable (returns `null` fields with `"blockchain_unavailable": true`).

### New Frontend API Function

`frontend/src/api/agreements.ts` gains `getEscrowState(agreementId: string)`.

## 3. Escrow State Stepper

### Component: `EscrowStepper.tsx`

**Location:** `frontend/src/components/shared/EscrowStepper.tsx`

**Props:**
```typescript
interface EscrowStepperProps {
  state: 'Funded' | 'Evaluated' | 'Accepted' | 'Rejected' | 'Expired';
  creationTxHash?: string;
  outcomeTxHash?: string;
  settlementTxHash?: string;
}
```

**Visual design:** Modeled exactly after `NegotiationProgress.tsx`:
- Horizontal row of step circles connected by lines
- Steps: Funded → Evaluated → (Accepted | Rejected | Expired)
- The third step label changes based on terminal state
- Completed steps: checkmark icon, `bg-ndai-500` fill, `bg-ndai-500` connector line
- Current step: pulsing ring animation (`animate-pulse ring-4 ring-ndai-200`)
- Future steps: gray outline, gray connector
- Below each completed step: truncated tx hash (`font-mono text-xs text-gray-400`) linked to `https://sepolia.basescan.org/tx/{hash}`

**Placement:** Top of agreement detail page (both buyer and seller), below the back link and title, above the status card. Only renders when `escrow_address` is present on the agreement.

## 4. Integration Points

### Agreement Detail Pages (Both Roles)

Current page structure (simplified):
```
Back Link
Title + StatusBadge
Status Card (metadata grid)
[Conditional sections based on status]
NegotiationProgress (when negotiating)
OutcomeDisplay (when completed)
VerificationPanel (when completed)
```

New structure:
```
Back Link
Title + StatusBadge
EscrowStepper (when escrow_address present)     ← NEW
Status Card (metadata grid)
[Conditional sections based on status]
NegotiationProgress (when negotiating)
OutcomeDisplay (when completed)
MechanismExplorer (always, below params)         ← NEW
VerificationPanel (when completed, now expanded) ← MODIFIED
```

### Data Flow

Agreement detail pages already fetch the agreement and outcome. New additions:
- `MechanismExplorer` is pure client-side, only needs props from already-fetched data
- `EscrowStepper` needs `escrow_address`, `escrow_tx_hash` from the agreement (already fetched) plus escrow state from the new API endpoint
- `VerificationPanel` expansion needs the same escrow state data

One new `useEffect` fetch: `getEscrowState(agreementId)` when `agreement.escrow_address` exists. Result feeds both `EscrowStepper` and `VerificationPanel`.

## 5. Data Pipeline Fixes (Prerequisites)

These fields exist in ORM models but are not plumbed through to API responses or frontend types. Must be added before the new components can work.

### 5.1 Add escrow fields to AgreementResponse

**Backend (`ndai/api/schemas/agreement.py`):** Add to `AgreementResponse`:
```python
    escrow_address: str | None = None
    escrow_tx_hash: str | None = None
```

**Backend (`ndai/api/routers/agreements.py`):** Add these fields to the `_agreement_response()` helper so they're mapped from the ORM model.

**Frontend (`frontend/src/api/types.ts` or equivalent):** Add to the `AgreementResponse` TypeScript interface:
```typescript
    escrow_address?: string | null;
    escrow_tx_hash?: string | null;
```

### 5.2 Add omega_hat and buyer_valuation to NegotiationOutcomeResponse

**Backend (`ndai/api/schemas/agreement.py`):** Add to `NegotiationOutcomeResponse`:
```python
    omega_hat: float | None = None
    buyer_valuation: float | None = None
```

**Backend (`ndai/api/routers/negotiations.py`):** In the outcome persistence and response logic, include `omega_hat` from `result.omega_hat` and `buyer_valuation` from `result.buyer_valuation`.

**Frontend types:** Add matching fields.

### 5.3 MechanismExplorer initialization fallbacks

When no outcome exists yet (pre-negotiation), the sliders initialize from:
- `budgetCap` → `agreement.budget_cap` (always available after buyer sets params)
- `alpha0` → `agreement.alpha_0` (available after seller/buyer sets params)
- `omegaHat` → `0.5` (sensible default — no outcome yet)
- `buyerValuation` → `0.5` (sensible default)

When outcome exists (post-negotiation), override with actual values from outcome.

### 5.4 Security Capacity display

The Security Capacity result card uses fixed default security parameters (`k=3, p=0.005, c=7.5B, gamma=1`) from the project's `Settings` class. These are NOT exposed as sliders — they're environment config, not user-tunable. The `securityCapacity()` function is called once with these defaults to display the Phi value. If the user wants to explore security params, that's a future enhancement.

### 5.5 VerificationPanel props extension

The existing `VerificationPanel` gains optional props for escrow data:
```typescript
interface VerificationPanelProps {
  verification: VerificationData | null | undefined;
  escrowData?: EscrowStateResponse | null;  // NEW — on-chain settlement data
}
```

The "On-Chain Settlement" accordion section only renders when `escrowData` is provided and non-null. Other consumers of `VerificationPanel` are unaffected (they don't pass `escrowData`).

### 5.6 VerificationPanel not currently on agreement pages

Neither `BuyerAgreementDetailPage` nor `SellerAgreementDetailPage` currently renders `VerificationPanel`. The integration work must add the import and conditional rendering on both pages (render when agreement status starts with `completed_`).

### 5.7 Bilateral price clarification

The Mechanism Explorer uses the **bilateral** Nash bargaining price from `compute_bilateral_price()`: `P* = (v_b + alpha_0 * omega_hat) / 2`. The traditional unilateral formula `P* = theta * omega_hat` is a special case when `v_b = omega_hat`. The explorer allows `v_b` to vary independently, which is the correct behavior for exploring the mechanism.

### 5.8 "Verify Attestation" button

The "Verify Attestation" button in the VerificationPanel simply calls `GET /agreements/{id}/escrow-state` and refreshes the displayed on-chain state. It does NOT perform cryptographic verification (that would require PCR/nonce/outcome bytes the frontend doesn't have). The button is labeled **"Refresh On-Chain State"** to accurately describe its behavior.

## 6. File Map

```
frontend/src/utils/mechanism.ts                           # NEW — Nash math functions
frontend/src/components/negotiation/MechanismExplorer.tsx  # NEW — parameter playground
frontend/src/components/shared/EscrowStepper.tsx           # NEW — escrow state stepper
frontend/src/components/shared/VerificationPanel.tsx       # MODIFIED — add on-chain section
frontend/src/api/agreements.ts                             # MODIFIED — add getEscrowState()
frontend/src/api/types.ts (or equivalent)                  # MODIFIED — add escrow + outcome fields
frontend/src/pages/buyer/BuyerAgreementDetailPage.tsx      # MODIFIED — add new components
frontend/src/pages/seller/SellerAgreementDetailPage.tsx    # MODIFIED — add new components
ndai/api/schemas/agreement.py                              # MODIFIED — add escrow + outcome fields
ndai/api/routers/agreements.py                             # MODIFIED — add escrow-state endpoint, map escrow fields
ndai/api/routers/negotiations.py                           # MODIFIED — include omega_hat/buyer_valuation in outcome
```

## 6. Testing

- `tests/unit/test_mechanism_math.ts` — Verify TypeScript math matches Python engine output for known inputs (or just test via Python unit test that imports the same formulas)
- `tests/unit/test_escrow_state_endpoint.py` — Mock EscrowClient, verify API returns correct shape
- Existing frontend build (`npm run build`) must pass
- Visual verification via wet test after deployment
