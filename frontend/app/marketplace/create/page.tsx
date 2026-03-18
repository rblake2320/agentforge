"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listAgents, createListing } from "@/lib/api";
import type { Agent } from "@/lib/types";
import Nav from "@/components/nav";

export default function CreateListingPage() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [form, setForm] = useState({
    agent_id: "",
    title: "",
    description: "",
    price_dollars: "0",
    license_type: "perpetual",
    max_clones: "100",
    category: "assistant",
    tags: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }
    listAgents().then(setAgents).catch((e) => setError(e.message));
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      await createListing({
        agent_id: form.agent_id,
        title: form.title,
        description: form.description,
        price_cents: Math.round(parseFloat(form.price_dollars) * 100),
        license_type: form.license_type,
        max_clones: parseInt(form.max_clones),
        category: form.category,
        tags: form.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      router.push("/marketplace");
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const field = (label: string, children: React.ReactNode) => (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      {children}
    </div>
  );

  const inputCls = "w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500";

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">List Agent on Marketplace</h1>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {field("Select Agent",
            <select
              required
              value={form.agent_id}
              onChange={(e) => setForm({ ...form, agent_id: e.target.value })}
              className={inputCls}
            >
              <option value="">Choose an agent…</option>
              {agents.map((a) => (
                <option key={a.agent_id} value={a.agent_id}>{a.display_name}</option>
              ))}
            </select>
          )}

          {field("Listing Title",
            <input
              type="text"
              required
              maxLength={255}
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              className={inputCls}
              placeholder="Expert Research Assistant"
            />
          )}

          {field("Description",
            <textarea
              rows={4}
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className={inputCls}
              placeholder="What does this agent do? What makes it special?"
            />
          )}

          <div className="grid grid-cols-2 gap-4">
            {field("Price (USD)",
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.price_dollars}
                onChange={(e) => setForm({ ...form, price_dollars: e.target.value })}
                className={inputCls}
              />
            )}
            {field("License Type",
              <select
                value={form.license_type}
                onChange={(e) => setForm({ ...form, license_type: e.target.value })}
                className={inputCls}
              >
                <option value="perpetual">Perpetual</option>
                <option value="subscription">Subscription (30 days)</option>
                <option value="per_use">Per Use (100 calls)</option>
              </select>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {field("Category",
              <select
                value={form.category}
                onChange={(e) => setForm({ ...form, category: e.target.value })}
                className={inputCls}
              >
                {["assistant", "code", "research", "data", "creative", "utility"].map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            )}
            {field("Max Clones",
              <input
                type="number"
                min="1"
                value={form.max_clones}
                onChange={(e) => setForm({ ...form, max_clones: e.target.value })}
                className={inputCls}
              />
            )}
          </div>

          {field("Tags (comma-separated)",
            <input
              type="text"
              value={form.tags}
              onChange={(e) => setForm({ ...form, tags: e.target.value })}
              className={inputCls}
              placeholder="research, gpt-4, rag, multilingual"
            />
          )}

          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4 text-xs text-gray-400">
            <p className="font-semibold text-gray-300 mb-1">Platform fee: 20%</p>
            <p>You receive {(parseFloat(form.price_dollars || "0") * 0.8).toFixed(2)} USD per license sold.</p>
          </div>

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={() => router.back()} className="flex-1 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="flex-1 px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition">
              {loading ? "Creating…" : "List Agent"}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
