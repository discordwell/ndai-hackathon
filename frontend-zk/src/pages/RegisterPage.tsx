import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { register as apiRegister } from "../api/auth";

export function RegisterPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const response = await apiRegister(email, password, name || undefined);
      login(response);
      window.location.hash = "#/browse";
    } catch (err: any) {
      setError(err.detail || "Registration failed");
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

        <h2 className="font-mono text-label mb-6">REGISTER</h2>

        {error && (
          <div className="border-2 border-zk-danger p-3 mb-4 font-mono text-sm text-zk-danger">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="zk-label">DISPLAY NAME</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="zk-input"
              placeholder="Optional"
            />
          </div>
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
              minLength={8}
            />
          </div>
          <button type="submit" disabled={loading} className="zk-btn-accent w-full disabled:opacity-50">
            {loading ? "..." : "CREATE ACCOUNT"}
          </button>
        </form>

        <p className="font-mono text-xs text-zk-muted mt-6">
          Already have an account? <a href="#/login">Login</a>
        </p>
      </div>
    </div>
  );
}
