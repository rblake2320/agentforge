"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { getAgent, getTrustProfile } from "@/lib/api";
import type { AgentDetail, TrustProfile } from "@/lib/types";
import Nav from "@/components/nav";

// ─── Constants ────────────────────────────────────────────────────────────────

const TRUST_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  elite:       { bg: "bg-purple-900/30",  text: "text-purple-400",  border: "border-purple-500" },
  verified:    { bg: "bg-emerald-900/30", text: "text-emerald-400", border: "border-emerald-500" },
  trusted:     { bg: "bg-blue-900/30",    text: "text-blue-400",    border: "border-blue-500"   },
  provisional: { bg: "bg-yellow-900/30", text: "text-yellow-400",  border: "border-yellow-500" },
  untrusted:   { bg: "bg-red-900/30",     text: "text-red-400",     border: "border-red-500"    },
};

const RUNTIME_COLORS: Record<string, string> = {
  nim:    "bg-green-900/40 text-green-400 border-green-800",
  ollama: "bg-blue-900/40 text-blue-400 border-blue-800",
  "21st": "bg-purple-900/40 text-purple-400 border-purple-800",
};

const TYPE_ICONS: Record<string, string> = {
  assistant:  "🤖",
  worker:     "⚙️",
  researcher: "🔬",
  analyst:    "📊",
  coder:      "💻",
  custom:     "✨",
};

type Tab = "identity" | "capabilities" | "certificate";

// ─── Sub-components ───────────────────────────────────────────────────────────

function CopyButton({ value, label }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  };

  return (
    <button
      onClick={copy}
      className="text-xs px-2.5 py-1 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-lg text-gray-400 hover:text-gray-200 transition-colors whitespace-nowrap"
    >
      {copied ? "Copied!" : label ?? "Copy"}
    </button>
  );
}

function JsonViewer({ data, collapsed = true }: { data: Record<string, unknown>; collapsed?: boolean }) {
  const [open, setOpen] = useState(!collapsed);
  const formatted = JSON.stringify(data, null, 2);

  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-gray-900 hover:bg-gray-800/80 text-xs text-gray-400 transition-colors"
      >
        <span className="font-mono">{open ? "▼" : "▶"} {open ? "Collapse" : "Expand"} JSON</span>
        <span className="text-gray-600">{Object.keys(data).length} keys</span>
      </button>
      {open && (
        <pre className="bg-gray-950 text-xs text-gray-300 font-mono p-4 overflow-x-auto max-h-80 leading-relaxed">
          {formatted}
        </pre>
      )}
    </div>
  );
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1.5">
        <span>{label}</span>
        <span className="font-mono">{score.toFixed(1)}</span>
      </div>
      <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
        <div
          className={`h-full ${color} rounded-full transition-all duration-700`}
          style={{ width: `${Math.min(score, 100)}%` }}
        />
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function AgentDetailPage() {
  const params = useParams();
  const agentId = params.id as string;
  const router = useRouter();

  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [trust, setTrust] = useState<TrustProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<Tab>("identity");

  const load = useCallback(() => {
    Promise.all([getAgent(agentId), getTrustProfile(agentId)])
      .then(([a, t]) => {
        setAgent(a);
        setTrust(t);
      })
      .catch((e: unknown) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [agentId]);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.push("/auth/login");
      return;
    }
    load();
  }, [load, router]);

  const handleVerify = async () => {
    setVerifying(true);
    setVerifyResult(null);
    try {
      const token = localStorage.getItem("access_token");
      const res = await fetch(`/api/v1/agents/${agentId}/verify`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      });
      if (res.ok) {
        setVerifyResult("Identity verified — signature is valid.");
      } else {
        const data = await res.json().catch(() => ({}));
        setVerifyResult(`Verification failed: ${data.detail ?? res.statusText}`);
      }
    } catch (e: unknown) {
      setVerifyResult(`Error: ${(e as Error).message}`);
    } finally {
      setVerifying(false);
    }
  };

  const handleDownloadDID = () => {
    if (!agent) return;
    const blob = new Blob([JSON.stringify(agent.did_document, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `did-document-${agentId.slice(0, 8)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // ─── Loading / error states ──────────────────────────────────────────────

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-gray-400 text-sm">Loading agent identity…</p>
        </div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-center max-w-md">
          <p className="text-red-400 font-medium mb-2">Failed to load agent</p>
          <p className="text-gray-500 text-sm mb-6">{error || "Agent not found."}</p>
          <button
            onClick={() => router.back()}
            className="text-sm text-violet-400 hover:text-violet-300 transition-colors"
          >
            ← Go back
          </button>
        </div>
      </div>
    );
  }

  // ─── Derived values ──────────────────────────────────────────────────────

  const runtimeColor = RUNTIME_COLORS[agent.preferred_runtime] ?? "bg-gray-800 text-gray-400 border-gray-700";
  const typeIcon = TYPE_ICONS[agent.agent_type] ?? "🤖";
  const trustColors = TRUST_COLORS[trust?.trust_level ?? "provisional"];

  const tabs: { id: Tab; label: string }[] = [
    { id: "identity", label: "Identity" },
    { id: "capabilities", label: "Capabilities" },
    { id: "certificate", label: "Certificate" },
  ];

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />

      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Back */}
        <button
          onClick={() => router.back()}
          className="text-xs text-gray-500 hover:text-gray-300 mb-6 flex items-center gap-1.5 transition-colors"
        >
          ← Back
        </button>

        {/* ── Hero card ─────────────────────────────────────────────────── */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-7 mb-6">
          <div className="flex flex-col sm:flex-row sm:items-start gap-5">
            {/* Icon + name */}
            <div className="flex items-center gap-4 flex-1">
              <div className="w-14 h-14 bg-violet-950 border border-violet-800 rounded-2xl flex items-center justify-center text-3xl flex-shrink-0">
                {typeIcon}
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-100">{agent.display_name}</h1>
                <p className="text-sm text-gray-400 capitalize mt-0.5">{agent.agent_type}</p>
                {agent.purpose && (
                  <p className="text-sm text-gray-500 mt-1.5 max-w-lg">{agent.purpose}</p>
                )}
              </div>
            </div>

            {/* Badges + actions */}
            <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end">
              <span
                className={`text-xs px-2.5 py-1 rounded-full border font-medium ${
                  agent.is_active
                    ? "bg-emerald-900/40 text-emerald-400 border-emerald-800"
                    : "bg-gray-800 text-gray-500 border-gray-700"
                }`}
              >
                {agent.is_active ? "Active" : "Inactive"}
              </span>
              <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${runtimeColor}`}>
                {agent.preferred_runtime}
              </span>
              <Link
                href={`/agents/${agentId}/chat`}
                className="text-xs px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white rounded-lg font-medium transition-colors mt-1"
              >
                💬 Chat
              </Link>
              <Link
                href="/marketplace/create"
                className="text-xs px-3 py-1.5 bg-violet-700 hover:bg-violet-600 text-white rounded-lg font-medium transition-colors mt-1"
              >
                List on Marketplace
              </Link>
            </div>
          </div>

          {/* DID URI */}
          <div className="mt-6 p-4 bg-gray-950 border border-gray-800 rounded-xl">
            <div className="flex items-center justify-between gap-3 mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">DID URI</span>
              <CopyButton value={agent.did_uri} label="Copy DID" />
            </div>
            <p className="font-mono text-sm text-violet-300 break-all">{agent.did_uri}</p>
          </div>

          {/* Key fingerprint */}
          <div className="mt-3 p-4 bg-gray-950 border border-gray-800 rounded-xl">
            <div className="flex items-center justify-between gap-3 mb-2">
              <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Key Fingerprint
                <span className="ml-2 text-gray-700 font-normal normal-case">{agent.key_algorithm}</span>
              </span>
              <CopyButton value={agent.key_fingerprint} label="Copy" />
            </div>
            <p className="font-mono text-sm text-gray-300 break-all">{agent.key_fingerprint}</p>
          </div>

          {/* Metadata row */}
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Model</p>
              <p className="text-xs font-mono text-gray-300">{agent.model_version || "—"}</p>
            </div>
            <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Capabilities</p>
              <p className="text-sm font-bold text-violet-400">{agent.capabilities.length}</p>
            </div>
            <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Public</p>
              <p className="text-xs text-gray-300">{agent.is_public ? "Yes" : "No"}</p>
            </div>
            <div className="bg-gray-950 border border-gray-800 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-500 mb-1">Born</p>
              <p className="text-xs text-gray-300">{new Date(agent.created_at).toLocaleDateString()}</p>
            </div>
          </div>
        </div>

        {/* ── Tabs ──────────────────────────────────────────────────────── */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden mb-6">
          {/* Tab bar */}
          <div className="flex border-b border-gray-800">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-3.5 text-sm font-medium transition-colors ${
                  activeTab === tab.id
                    ? "text-violet-400 border-b-2 border-violet-500 bg-violet-950/20"
                    : "text-gray-500 hover:text-gray-300"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="p-6">
            {/* ── Identity tab ── */}
            {activeTab === "identity" && (
              <div className="space-y-5">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    DID Document
                  </h3>
                  <JsonViewer data={agent.did_document} collapsed />
                </div>
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Verifiable Credential
                  </h3>
                  <JsonViewer data={agent.verifiable_credential} collapsed />
                </div>
              </div>
            )}

            {/* ── Capabilities tab ── */}
            {activeTab === "capabilities" && (
              <div className="space-y-6">
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Capabilities
                  </h3>
                  {agent.capabilities.length === 0 ? (
                    <p className="text-sm text-gray-500 italic">No capabilities declared.</p>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {agent.capabilities.map((cap: string) => (
                        <span
                          key={cap}
                          className="text-sm bg-violet-950/50 border border-violet-900 text-violet-300 px-3 py-1.5 rounded-lg"
                        >
                          {cap}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Behavioral Signature
                  </h3>
                  <JsonViewer data={agent.behavioral_signature} collapsed />
                </div>
              </div>
            )}

            {/* ── Certificate tab ── */}
            {activeTab === "certificate" && (
              <div className="space-y-5">
                <p className="text-sm text-gray-400">
                  Download the W3C DID Document or verify this agent&apos;s cryptographic identity
                  against the AgentForge registry.
                </p>

                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={handleDownloadDID}
                    className="flex items-center gap-2 px-4 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 rounded-xl text-sm font-medium text-gray-200 transition-colors"
                  >
                    <span>Download DID Document</span>
                    <span className="text-gray-500 text-xs">.json</span>
                  </button>

                  <button
                    onClick={handleVerify}
                    disabled={verifying}
                    className="flex items-center gap-2 px-4 py-2.5 bg-violet-700 hover:bg-violet-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl text-sm font-medium text-white transition-colors"
                  >
                    {verifying ? (
                      <>
                        <div className="w-3.5 h-3.5 border border-white/40 border-t-white rounded-full animate-spin" />
                        Verifying…
                      </>
                    ) : (
                      "Verify Identity"
                    )}
                  </button>
                </div>

                {verifyResult && (
                  <div
                    className={`p-4 rounded-xl text-sm border ${
                      verifyResult.toLowerCase().includes("verified")
                        ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
                        : "bg-red-950/40 border-red-800 text-red-300"
                    }`}
                  >
                    {verifyResult}
                  </div>
                )}

                <div className="border-t border-gray-800 pt-5">
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
                    Verifiable Credential (preview)
                  </h3>
                  <JsonViewer data={agent.verifiable_credential} collapsed />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Trust score widget ─────────────────────────────────────────── */}
        {trust && (
          <div className={`${trustColors.bg} border ${trustColors.border} rounded-2xl p-6 mb-6`}>
            <div className="flex items-center justify-between mb-5">
              <div>
                <h2 className="text-sm font-bold text-gray-100">Trust Score</h2>
                <p className="text-xs text-gray-500 mt-0.5">
                  Last calculated {new Date(trust.calculated_at).toLocaleString()}
                </p>
              </div>
              <div className="text-right">
                <p className={`text-4xl font-bold ${trustColors.text}`}>{trust.overall_score.toFixed(0)}</p>
                <p className={`text-xs font-semibold uppercase ${trustColors.text} mt-0.5`}>
                  {trust.trust_level}
                </p>
              </div>
            </div>

            <div className="space-y-3 mb-5">
              <ScoreBar label="Technical Trust" score={trust.technical_trust} />
              <ScoreBar label="Reliability Trust" score={trust.reliability_trust} />
              <ScoreBar label="Security Trust" score={trust.security_trust} />
            </div>

            <div className="grid grid-cols-3 gap-3 mb-5">
              <div className="bg-gray-900/60 rounded-xl p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">Tamper Violations</p>
                <p
                  className={`font-bold text-lg ${
                    trust.tamper_violations > 0 ? "text-red-400" : "text-emerald-400"
                  }`}
                >
                  {trust.tamper_violations}
                </p>
              </div>
              <div className="bg-gray-900/60 rounded-xl p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">Uptime</p>
                <p className="font-bold text-lg text-emerald-400">{trust.uptime_pct.toFixed(1)}%</p>
              </div>
              <div className="bg-gray-900/60 rounded-xl p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">Heartbeats</p>
                <p className="font-bold text-lg text-blue-400">{trust.heartbeat_checks}</p>
              </div>
            </div>

            <Link
              href={`/trust/${agentId}`}
              className={`block text-center text-sm py-2 rounded-xl border ${trustColors.border} ${trustColors.text} hover:bg-gray-900/40 transition-colors font-medium`}
            >
              View Full Trust Profile →
            </Link>
          </div>
        )}

        {/* ── Marketplace CTA ────────────────────────────────────────────── */}
        <div className="bg-gradient-to-r from-violet-950/60 via-gray-900 to-violet-950/60 border border-violet-900/50 rounded-2xl p-6 text-center">
          <h3 className="font-semibold text-gray-100 mb-2">Ready to monetize this agent?</h3>
          <p className="text-sm text-gray-400 mb-4">
            List it on the marketplace. Buyers receive a cryptographically signed clone with a
            unique license key.
          </p>
          <Link
            href="/marketplace/create"
            className="inline-block px-6 py-2.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-semibold text-sm transition-colors"
          >
            List on Marketplace
          </Link>
        </div>
      </main>
    </div>
  );
}
