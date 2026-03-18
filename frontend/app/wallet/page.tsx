"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getWallet, createWallet, listAgents, getTrustProfile } from "@/lib/api";
import type { Wallet, Agent, TrustProfile } from "@/lib/types";
import Nav from "@/components/nav";

const TRUST_COLORS: Record<string, string> = {
  elite: "text-purple-400 border-purple-400",
  verified: "text-emerald-400 border-emerald-400",
  trusted: "text-blue-400 border-blue-400",
  provisional: "text-yellow-400 border-yellow-400",
  untrusted: "text-red-400 border-red-400",
};

function TrustBadge({ level, score }: { level: string; score: number }) {
  const cls = TRUST_COLORS[level] ?? "text-gray-400 border-gray-400";
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${cls}`}>
      {level.toUpperCase()} {Math.round(score)}
    </span>
  );
}

function HeartbeatPulse({ active }: { active: boolean }) {
  return (
    <span className={`inline-block w-2.5 h-2.5 rounded-full ${active ? "bg-emerald-400 animate-pulse" : "bg-gray-600"}`} />
  );
}

function CreateWalletCard({ onCreated }: { onCreated: (w: Wallet) => void }) {
  const [passphrase, setPassphrase] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleCreate = async () => {
    if (passphrase.length < 8) { setError("Passphrase must be at least 8 characters"); return; }
    if (passphrase !== confirm) { setError("Passphrases do not match"); return; }
    setLoading(true);
    setError("");
    try {
      const w = await createWallet(passphrase);
      onCreated(w);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create wallet");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-16">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
        <div className="text-4xl mb-4">🔐</div>
        <h2 className="text-xl font-bold mb-2">Create Your Wallet</h2>
        <p className="text-gray-400 text-sm mb-6">
          Your wallet encrypts agent private keys using XChaCha20-Poly1305 with Argon2id key derivation.
          Choose a strong passphrase — you'll need it to access your keys.
        </p>
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 mb-4 text-sm">{error}</div>
        )}
        <div className="space-y-3 text-left">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Wallet Passphrase</label>
            <input
              type="password"
              value={passphrase}
              onChange={(e) => setPassphrase(e.target.value)}
              placeholder="min 8 characters"
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">Confirm Passphrase</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="repeat passphrase"
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
            />
          </div>
          <button
            onClick={handleCreate}
            disabled={loading || !passphrase || !confirm}
            className="w-full px-4 py-2.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-lg text-sm font-semibold transition mt-2"
          >
            {loading ? "Creating…" : "🔐 Create Wallet"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function WalletPage() {
  const router = useRouter();
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [walletMissing, setWalletMissing] = useState(false);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [profiles, setProfiles] = useState<Record<string, TrustProfile>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = () => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }

    Promise.all([getWallet().catch((e: Error) => {
      if (e.message.includes("wallet") || e.message.includes("404")) {
        setWalletMissing(true);
        return null;
      }
      throw e;
    }), listAgents()])
      .then(([w, agts]) => {
        if (w) setWallet(w);
        setAgents(agts);
        agts.forEach((a) =>
          getTrustProfile(a.agent_id)
            .then((p) => setProfiles((prev) => ({ ...prev, [a.agent_id]: p })))
            .catch(() => {})
        );
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => { loadData(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="animate-pulse text-gray-400">Loading wallet…</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-6xl mx-auto px-4 py-8">
        {walletMissing && !wallet ? (
          <CreateWalletCard onCreated={() => { setWalletMissing(false); setLoading(true); loadData(); }} />
        ) : (
          <>
            <div className="flex items-center justify-between mb-8">
              <div>
                <h1 className="text-2xl font-bold">Agent Wallet</h1>
                <p className="text-gray-400 text-sm mt-1">
                  {wallet ? `Wallet ${wallet.wallet_id.slice(0, 8)}… · ${agents.length} agents` : ""}
                </p>
              </div>
              <button
                onClick={() => router.push("/agents/create")}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium transition"
              >
                + Birth Agent
              </button>
            </div>

            {error && (
              <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6 text-sm">{error}</div>
            )}

            {agents.length === 0 ? (
              <div className="text-center py-20 text-gray-500">
                <p className="text-lg mb-2">No agents yet</p>
                <p className="text-sm">Birth your first agent to get started.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {agents.map((agent) => {
                  const profile = profiles[agent.agent_id];
                  const hasKey = wallet?.keys.some(
                    (k) => k.agent_id === agent.agent_id && !k.revoked_at
                  );
                  return (
                    <div
                      key={agent.agent_id}
                      onClick={() => router.push(`/agents/${agent.agent_id}`)}
                      className="bg-gray-900 border border-gray-800 rounded-xl p-5 cursor-pointer hover:border-violet-600 transition group"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <h3 className="font-semibold text-sm group-hover:text-violet-400 transition">
                            {agent.display_name}
                          </h3>
                          <p className="text-xs text-gray-500 font-mono mt-0.5">
                            {agent.key_fingerprint.slice(0, 16)}…
                          </p>
                        </div>
                        <HeartbeatPulse active={agent.is_active} />
                      </div>

                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {agent.capabilities.slice(0, 3).map((c) => (
                          <span key={c} className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full">
                            {c}
                          </span>
                        ))}
                      </div>

                      <div className="flex items-center justify-between text-xs">
                        {profile ? (
                          <TrustBadge level={profile.trust_level} score={profile.overall_score} />
                        ) : (
                          <span className="text-gray-600 text-xs">loading trust…</span>
                        )}
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${hasKey ? "bg-emerald-900/40 text-emerald-400" : "bg-gray-800 text-gray-500"}`}>
                            {hasKey ? "🔑 keyed" : "no key"}
                          </span>
                          <span className="text-gray-600">{agent.preferred_runtime}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {wallet && (
              <div className="mt-8 bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h2 className="text-sm font-semibold text-gray-300 mb-3">Wallet Keys</h2>
                {wallet.keys.length === 0 ? (
                  <p className="text-gray-600 text-sm">No keys stored. Birth an agent and store its private key here.</p>
                ) : (
                  <div className="space-y-2">
                    {wallet.keys.map((k) => (
                      <div key={k.key_id} className="flex items-center justify-between text-xs text-gray-400 border-b border-gray-800 pb-2">
                        <span className="font-mono">{k.key_id.slice(0, 12)}… (agent {k.agent_id.slice(0, 8)}…)</span>
                        <div className="flex items-center gap-2">
                          <span>v{k.key_version}</span>
                          {k.revoked_at ? (
                            <span className="text-red-400">revoked</span>
                          ) : (
                            <span className="text-emerald-400">active</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
