import React, { useState } from "react";
import { computePrice, computeTheta, securityCapacity, isDealViable, checkBudgetCap } from "../../utils/mechanism";

interface Props {
  initialBudgetCap?: number;
  initialAlpha0?: number;
  initialOmegaHat?: number;
  initialBuyerValue?: number;
}

export function MechanismExplorer({
  initialBudgetCap = 1.0,
  initialAlpha0 = 0.5,
  initialOmegaHat = 0.5,
  initialBuyerValue = 0.7,
}: Props) {
  const [budgetCap, setBudgetCap] = useState(initialBudgetCap);
  const [alpha0, setAlpha0] = useState(initialAlpha0);
  const [omegaHat, setOmegaHat] = useState(initialOmegaHat);
  const [buyerValue, setBuyerValue] = useState(initialBuyerValue);
  const [showFormula, setShowFormula] = useState(false);

  const price = computePrice(alpha0, omegaHat, buyerValue);
  const phi = securityCapacity();
  const viable = isDealViable(buyerValue, alpha0, omegaHat);
  const withinBudget = checkBudgetCap(price, budgetCap);
  const dealOk = viable && withinBudget;

  const phiDisplay = phi > 1e9
    ? (phi / 1e9).toFixed(1) + "B"
    : phi.toFixed(2);

  return (
    <div className="bg-ndai-50 rounded-xl border border-ndai-100 p-6">
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-gray-900">Mechanism Explorer</h2>
        <p className="text-sm text-gray-500 mt-1">
          Adjust parameters to explore Nash equilibrium pricing and deal viability.
        </p>
      </div>

      {/* Result cards */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        <div className="bg-white rounded-lg border border-ndai-100 p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Equilibrium Price</div>
          <div className="text-2xl font-bold text-ndai-600">{price.toFixed(4)}</div>
          <div className="text-xs text-gray-400 mt-1">P* = (v_b + α₀·ω̂) / 2</div>
        </div>

        <div className="bg-white rounded-lg border border-green-100 p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Security Capacity</div>
          <div className="text-2xl font-bold text-green-600">{phiDisplay}</div>
          <div className="text-xs text-gray-400 mt-1">Max securable value</div>
        </div>

        <div className="bg-white rounded-lg border border-gray-100 p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Deal Viable</div>
          <div className={`text-2xl font-bold ${dealOk ? "text-green-600" : "text-red-500"}`}>
            {dealOk ? "Yes" : "No"}
          </div>
          <div className="text-xs text-gray-400 mt-1">
            {!viable ? "Below reservation" : !withinBudget ? "Exceeds budget" : "All conditions met"}
          </div>
        </div>
      </div>

      {/* Sliders in 2x2 grid */}
      <div className="grid grid-cols-2 gap-3 mb-5">
        {/* Budget Cap */}
        <div className="bg-white rounded-lg border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Budget Cap</label>
            <span className="text-sm font-mono text-gray-900">{budgetCap.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.01}
            max={2.0}
            step={0.01}
            value={budgetCap}
            onChange={(e) => setBudgetCap(parseFloat(e.target.value))}
            className="w-full"
            style={{ accentColor: "#4c6ef5" }}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0.01</span>
            <span>2.0</span>
          </div>
        </div>

        {/* Reserve Price (alpha0) */}
        <div className="bg-white rounded-lg border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Reserve Price (α₀)</label>
            <span className="text-sm font-mono text-gray-900">{alpha0.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.01}
            max={1.0}
            step={0.01}
            value={alpha0}
            onChange={(e) => setAlpha0(parseFloat(e.target.value))}
            className="w-full"
            style={{ accentColor: "#f59e0b" }}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0.01</span>
            <span>1.0</span>
          </div>
        </div>

        {/* Disclosure (omegaHat) */}
        <div className="bg-white rounded-lg border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Disclosure (ω̂)</label>
            <span className="text-sm font-mono text-gray-900">{omegaHat.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.01}
            max={1.0}
            step={0.01}
            value={omegaHat}
            onChange={(e) => setOmegaHat(parseFloat(e.target.value))}
            className="w-full"
            style={{ accentColor: "#8b5cf6" }}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0.01</span>
            <span>1.0</span>
          </div>
        </div>

        {/* Buyer Valuation */}
        <div className="bg-white rounded-lg border border-gray-100 p-4">
          <div className="flex items-center justify-between mb-2">
            <label className="text-sm font-medium text-gray-700">Buyer Valuation (v_b)</label>
            <span className="text-sm font-mono text-gray-900">{buyerValue.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={0.01}
            max={1.0}
            step={0.01}
            value={buyerValue}
            onChange={(e) => setBuyerValue(parseFloat(e.target.value))}
            className="w-full"
            style={{ accentColor: "#22c55e" }}
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>0.01</span>
            <span>1.0</span>
          </div>
        </div>
      </div>

      {/* Collapsible formula section */}
      <div className="border-t border-ndai-100 pt-4">
        <button
          onClick={() => setShowFormula(!showFormula)}
          className="flex items-center gap-2 text-sm text-ndai-600 hover:text-ndai-700 font-medium"
        >
          <span>{showFormula ? "▾" : "▸"}</span>
          <span>Mechanism Formulas</span>
        </button>

        {showFormula && (
          <div className="mt-3 bg-white rounded-lg border border-gray-100 p-4 space-y-2 text-sm">
            <div className="flex items-center gap-3">
              <code className="bg-gray-50 px-2 py-1 rounded font-mono text-gray-700 text-xs">
                P* = (v_b + α₀·ω̂) / 2
              </code>
              <span className="text-gray-500 text-xs">Bilateral Nash equilibrium price</span>
            </div>
            <div className="flex items-center gap-3">
              <code className="bg-gray-50 px-2 py-1 rounded font-mono text-gray-700 text-xs">
                θ = (1 + α₀) / 2 = {computeTheta(alpha0).toFixed(4)}
              </code>
              <span className="text-gray-500 text-xs">Seller's bargaining share</span>
            </div>
            <div className="flex items-center gap-3">
              <code className="bg-gray-50 px-2 py-1 rounded font-mono text-gray-700 text-xs">
                viable: v_b ≥ α₀·ω̂ → {buyerValue.toFixed(2)} ≥ {(alpha0 * omegaHat).toFixed(2)}
              </code>
            </div>
            <div className="flex items-center gap-3">
              <code className="bg-gray-50 px-2 py-1 rounded font-mono text-gray-700 text-xs">
                budget: P* ≤ cap → {price.toFixed(4)} ≤ {budgetCap.toFixed(2)}
              </code>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
