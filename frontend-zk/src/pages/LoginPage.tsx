import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { login as apiLogin } from "../api/auth";

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
      const response = await apiLogin(email, password);
      login(response);
      window.location.hash = "#/browse";
    } catch (err: any) {
      setError(err.detail || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-sm">
        <a href="#/" className="font-mono font-extrabold text-2xl tracking-tighter no-underline text-zk-text block mb-8">
          ZDAYZK
        </a>

        <h2 className="font-mono text-label mb-6">LOGIN</h2>

        {error && (
          <div className="border-2 border-zk-danger p-3 mb-4 font-mono text-sm text-zk-danger">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="zk-label">EMAIL</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="zk-input"
              required
            />
          </div>
          <div>
            <label className="zk-label">PASSWORD</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="zk-input"
              required
            />
          </div>
          <button type="submit" disabled={loading} className="zk-btn-accent w-full disabled:opacity-50">
            {loading ? "..." : "ENTER"}
          </button>
        </form>

        <p className="font-mono text-xs text-zk-muted mt-6">
          No account? <a href="#/register">Register</a>
        </p>
      </div>
    </div>
  );
}
