"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createAgent, storeKey, getWallet, createWallet } from "../../../lib/api";

const AGENT_TYPES = [
  { value: "assistant", label: "Assistant", desc: "General-purpose conversational agent" },
  { value: "worker", label: "Worker", desc: "Executes tasks autonomously" },
  { value: "researcher", label: "Researcher", desc: "Finds and synthesizes information" },
  { value: "analyst", label: "Analyst", desc: "Analyzes data and generates insights" },
  { value: "coder", label: "Coder", desc: "Writes and reviews code" },
  { value: "custom", label: "Custom", desc: "Define your own role" },
];

const RUNTIMES = [
  { value: "nim", label: "NVIDIA NIM", desc: "Self-hosted, RTX 5090" },
  { value: "ollama", label: "Ollama", desc: "Local fallback" },
  { value: "21st", label: "21st.dev Cloud", desc: "Managed cloud runtime" },
];

export default function CreateAgentPage() {
  const router = useRouter();
  const [displayName, setDisplayName] = useState("");
  const [agentType, setAgentType] = useState("assistant");
  const [purpose, setPurpose] = useState("");
  const [capInput, setCapInput] = useState("");
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [runtime, setRuntime] = useState("nim");
  const [isPublic, setIsPublic] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [born, setBorn] = useState<{ agent: { agent_id: string; did_uri: string; key_fingerprint: string }; private_key_hex: string } | null>(null);
  const [keyCopied, setKeyCopied] = useState(false);
  const [walletPassphrase, setWalletPassphrase] = useState("");
  const [storeStatus, setStoreStatus] = useState<"idle" | "storing" | "stored" | "error">("idle");
  const [storeError, setStoreError] = useState("");

  function addCapability() {
    const cap = capInput.trim();
    if (cap && !capabilities.includes(cap)) {
      setCapabilities([...capabilities, cap]);
      setCapInput("");
    }
  }

  function removeCapability(cap: string) {
    setCapabilities(capabilities.filter((c) => c !== cap));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await createAgent({
        display_name: displayName,
        agent_type: agentType,
        purpose,
        capabilities,
        preferred_runtime: runtime,
        is_public: isPublic,
      });
      setBorn(result);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to birth agent");
    } finally {
      setLoading(false);
    }
  }

  function copyKey() {
    if (born) {
      navigator.clipboard.writeText(born.private_key_hex);
      setKeyCopied(true);
      setTimeout(() => setKeyCopied(false), 3000);
    }
  }

  async function handleStoreInWallet() {
    if (!born || !walletPassphrase) return;
    setStoreStatus("storing");
    setStoreError("");
    try {
      // Ensure wallet exists (create if not)
      try {
        await getWallet();
      } catch {
        await createWallet(walletPassphrase);
      }
      await storeKey(born.agent.agent_id, born.private_key_hex, walletPassphrase);
      setStoreStatus("stored");
    } catch (err: unknown) {
      setStoreStatus("error");
      setStoreError(err instanceof Error ? err.message : "Failed to store key");
    }
  }

  // Show key custody screen after successful birth
  if (born) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center px-4">
        <div className="w-full max-w-lg">
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-green-900 rounded-lg flex items-center justify-center text-green-400 text-xl">
                🎉
              </div>
              <div>
                <h2 className="font-bold text-zinc-100">Agent Born!</h2>
                <p className="text-sm text-zinc-400">{born.agent.did_uri}</p>
              </div>
            </div>

            <div className="bg-amber-950 border border-amber-800 rounded-lg p-4 mb-4">
              <p className="text-amber-400 text-sm font-medium mb-1">⚠️ Save Your Private Key Now</p>
              <p className="text-amber-300/70 text-xs">
                This private key will NEVER be shown again. It is not stored on our servers.
                Store it in your password manager or encrypted vault.
              </p>
            </div>

            <div className="bg-zinc-950 rounded-lg p-3 mb-4 font-mono text-xs text-zinc-300 break-all border border-zinc-700">
              {born.private_key_hex}
            </div>

            <div className="flex gap-3 mb-6">
              <button
                onClick={copyKey}
                className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 py-2 rounded-lg text-sm transition-colors"
              >
                {keyCopied ? "Copied!" : "Copy Key"}
              </button>
              <button
                onClick={() => {
                  const blob = new Blob(
                    [JSON.stringify({ agent_id: born.agent.agent_id, private_key_hex: born.private_key_hex }, null, 2)],
                    { type: "application/json" }
                  );
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `agentforge-key-${born.agent.agent_id.slice(0, 8)}.json`;
                  a.click();
                }}
                className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 py-2 rounded-lg text-sm transition-colors"
              >
                Download Key
              </button>
            </div>

            <div className="text-sm text-zinc-400 mb-4">
              <div className="flex justify-between py-1 border-b border-zinc-800">
                <span>Fingerprint</span>
                <span className="font-mono text-xs text-zinc-300">{born.agent.key_fingerprint.slice(0, 24)}...</span>
              </div>
            </div>

            {/* Wallet storage section */}
            {storeStatus !== "stored" ? (
              <div className="mb-4 border border-zinc-700 rounded-lg p-4">
                <p className="text-sm font-medium text-zinc-300 mb-2">🔐 Store Key in Wallet</p>
                <p className="text-xs text-zinc-500 mb-3">
                  Encrypt and store this key in your AgentForge wallet so it&apos;s retrievable later.
                </p>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={walletPassphrase}
                    onChange={(e) => setWalletPassphrase(e.target.value)}
                    placeholder="Wallet passphrase"
                    className="flex-1 bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:border-green-500"
                  />
                  <button
                    onClick={handleStoreInWallet}
                    disabled={storeStatus === "storing" || !walletPassphrase}
                    className="bg-green-700 hover:bg-green-600 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
                  >
                    {storeStatus === "storing" ? "Storing…" : "Store"}
                  </button>
                </div>
                {storeStatus === "error" && (
                  <p className="text-xs text-red-400 mt-2">{storeError}</p>
                )}
              </div>
            ) : (
              <div className="mb-4 bg-green-950 border border-green-800 rounded-lg p-3 text-sm text-green-400">
                ✓ Key stored securely in your wallet
              </div>
            )}

            <button
              onClick={() => router.push("/dashboard")}
              className="w-full bg-green-600 hover:bg-green-500 text-white py-2.5 rounded-lg font-medium transition-colors"
            >
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      <nav className="border-b border-zinc-800 px-6 py-4 flex items-center gap-4">
        <Link href="/dashboard" className="text-zinc-400 hover:text-zinc-100 text-sm transition-colors">
          ← Dashboard
        </Link>
        <span className="text-zinc-600">/</span>
        <span className="text-sm text-zinc-100">Birth Agent</span>
      </nav>

      <main className="max-w-2xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-zinc-100">Birth a New Agent</h1>
          <p className="text-sm text-zinc-400 mt-1">
            Creates an Ed25519 keypair, W3C DID Document, and Verifiable Credential.
          </p>
        </div>

        {error && (
          <div className="bg-red-950 border border-red-800 text-red-400 text-sm px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1">Agent Name *</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              maxLength={255}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-green-500"
              placeholder="Research Assistant v1"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">Agent Type *</label>
            <div className="grid grid-cols-2 gap-2">
              {AGENT_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setAgentType(t.value)}
                  className={`text-left p-3 rounded-lg border transition-colors ${
                    agentType === t.value
                      ? "border-green-500 bg-green-950 text-zinc-100"
                      : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-500"
                  }`}
                >
                  <div className="text-sm font-medium">{t.label}</div>
                  <div className="text-xs opacity-70 mt-0.5">{t.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1">Purpose</label>
            <textarea
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              rows={2}
              className="w-full bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-green-500 resize-none"
              placeholder="What will this agent do?"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-1">Capabilities</label>
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={capInput}
                onChange={(e) => setCapInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addCapability())}
                className="flex-1 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-zinc-100 focus:outline-none focus:border-green-500"
                placeholder="web_search, code_execution..."
              />
              <button
                type="button"
                onClick={addCapability}
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-4 py-2 rounded-lg text-sm transition-colors"
              >
                Add
              </button>
            </div>
            {capabilities.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {capabilities.map((cap) => (
                  <span
                    key={cap}
                    className="bg-zinc-800 text-zinc-300 text-xs px-2 py-1 rounded-full flex items-center gap-1"
                  >
                    {cap}
                    <button
                      type="button"
                      onClick={() => removeCapability(cap)}
                      className="text-zinc-500 hover:text-zinc-300"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-zinc-300 mb-2">Runtime</label>
            <div className="grid grid-cols-3 gap-2">
              {RUNTIMES.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => setRuntime(r.value)}
                  className={`text-left p-3 rounded-lg border transition-colors ${
                    runtime === r.value
                      ? "border-green-500 bg-green-950 text-zinc-100"
                      : "border-zinc-700 bg-zinc-900 text-zinc-400 hover:border-zinc-500"
                  }`}
                >
                  <div className="text-sm font-medium">{r.label}</div>
                  <div className="text-xs opacity-70 mt-0.5">{r.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setIsPublic(!isPublic)}
              className={`w-10 h-6 rounded-full transition-colors ${isPublic ? "bg-green-600" : "bg-zinc-700"}`}
            >
              <div
                className={`w-4 h-4 bg-white rounded-full mx-1 transition-transform ${isPublic ? "translate-x-4" : ""}`}
              />
            </button>
            <div>
              <div className="text-sm font-medium text-zinc-300">Public Agent</div>
              <div className="text-xs text-zinc-500">Visible in the marketplace</div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !displayName.trim()}
            className="w-full bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white py-3 rounded-lg font-medium transition-colors"
          >
            {loading ? "Generating Keys & Birthing Agent..." : "Birth Agent"}
          </button>
        </form>
      </main>
    </div>
  );
}
