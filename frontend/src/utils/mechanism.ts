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

/** Security capacity: max securable value given TEE parameters. */
export function securityCapacity(
  k: number = 3, p: number = 0.005, c: number = 7_500_000_000, gamma: number = 1,
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
