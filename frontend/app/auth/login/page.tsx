"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { login } from "../../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const data = await login(email, password);
      localStorage.setItem("access_token", data.access_token);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="inline-flex items-center gap-2 mb-6">
            <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center text-black font-bold text-sm">
              AF
            </div>
            <span className="font-semibold text-zinc-100">AgentForge</span>
          </Link>
          <h1 className="text-2xl font-bold text-zinc-100">Sign in to your account</h1>
          <p className="text-sm text-zinc-400 mt-2">
            Don&apos;t have an account?{" "}
            <Link href="/auth/register" className="text-green-400 hover:text-green-300">
              Create one
            </Link>
          </p>
        </div>
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
          {error && (
            <div className="bg-red-950 border border-red-800 text-red-400 text-sm px-4 py-3 rounded-lg mb-4">
              {error}
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-green-500"
                placeholder="agent@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-zinc-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-green-500"
                placeholder="••••••••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white py-2.5 rounded-lg font-medium transition-colors"
            >
              {loading ? "Signing in..." : "Sign In"}
            </button>
          </form>
        </div>
      </div>
    </main>
  );
}
