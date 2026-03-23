import React, { useState } from "react";
import { login as apiLogin } from "../api/auth";
import { useAuth } from "../contexts/AuthContext";

function NdaiLogo({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Shield shape */}
      <path
        d="M24 4L6 12v12c0 11 8 18 18 22 10-4 18-11 18-22V12L24 4z"
        fill="url(#shield-gradient)"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      {/* Lock keyhole */}
      <circle cx="24" cy="22" r="4" fill="none" stroke="white" strokeWidth="1.5" />
      <rect x="22.5" y="25" width="3" height="5" rx="1" fill="white" />
      <defs>
        <linearGradient id="shield-gradient" x1="24" y1="4" x2="24" y2="46" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4c6ef5" />
          <stop offset="1" stopColor="#364fc7" />
        </linearGradient>
      </defs>
    </svg>
  );
}

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await apiLogin({ email, password });
      login(res);
      window.location.hash = res.role === "seller" ? "#/seller" : "#/buyer";
    } catch (err: any) {
      setError(err.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-ndai-900 via-ndai-800 to-ndai-700">
      <div className="w-full max-w-md animate-scaleIn">
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <div className="flex flex-col items-center mb-8">
            <NdaiLogo className="w-14 h-14 text-ndai-700 mb-3" />
            <h1 className="text-2xl font-bold text-gray-900">NDAI</h1>
            {/* human-requested tagline */}
            <p className="text-sm text-gray-500 mt-1">
              Arrow's Paradox, Solved.
            </p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="bg-red-50 text-red-700 p-3 rounded-lg text-sm">
                {error}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-ndai-500 focus:border-transparent outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 px-4 bg-ndai-600 text-white rounded-lg hover:bg-ndai-700 disabled:opacity-50 font-medium transition-colors"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
          <p className="mt-6 text-center text-sm text-gray-500">
            Don't have an account?{" "}
            <a
              href="#/register"
              className="text-ndai-600 hover:text-ndai-700 font-medium"
            >
              Register
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
