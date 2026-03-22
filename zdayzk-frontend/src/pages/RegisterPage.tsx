import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import { Input } from "../components/design-system/Input";
import { Button } from "../components/design-system/Button";
import { ApiError } from "../api/client";

export function RegisterPage() {
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await register(email, password, displayName || undefined);
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
            Create account
          </h1>
          <p className="text-sm text-white/40">
            Join the vulnerability marketplace
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Display name"
            type="text"
            placeholder="Optional handle"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            autoComplete="name"
          />

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
            placeholder="Min 8 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
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
            Create account
          </Button>
        </form>

        <p className="text-center text-sm text-white/40">
          Already have an account?{" "}
          <a
            href="#/login"
            className="text-accent-400 hover:text-accent-300 transition-colors"
          >
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}
