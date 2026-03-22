import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { Input } from "../components/design-system/Input";
import { Button } from "../components/design-system/Button";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      window.location.hash = "#/dashboard";
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="w-full max-w-sm animate-fade-in">
      <div className="glass-card p-8 space-y-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-mono font-bold text-white">
            Sign in
          </h1>
          <p className="text-sm text-white/40">
            Access the vulnerability marketplace
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Email"
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />

          <Input
            label="Password"
            type="password"
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
          />

          {error && (
            <p className="text-sm text-danger-400 text-center">{error}</p>
          )}

          <Button
            type="submit"
            fullWidth
            loading={loading}
            size="lg"
          >
            Sign in
          </Button>
        </form>

        <p className="text-center text-sm text-white/40">
          No account?{" "}
          <a
            href="#/register"
            className="text-accent-400 hover:text-accent-300 transition-colors"
          >
            Register
          </a>
        </p>
      </div>
    </div>
  );
}
