"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getTrustProfile, recalculateTrust, getAgent, listAgentSkills, listSkillConnectors } from "@/lib/api";
import type { TrustProfile, AgentDetail, SkillBinding, SkillConnector } from "@/lib/types";
import Nav from "@/components/nav";

const TRUST_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  elite:       { bg: "bg-purple-900/30", text: "text-purple-400",  border: "border-purple-500" },
  verified:    { bg: "bg-emerald-900/30", text: "text-emerald-400", border: "border-emerald-500" },
  trusted:     { bg: "bg-blue-900/30",   text: "text-blue-400",    border: "border-blue-500"   },
  provisional: { bg: "bg-yellow-900/30", text: "text-yellow-400",  border: "border-yellow-500" },
  untrusted:   { bg: "bg-red-900/30",    text: "text-red-400",     border: "border-red-500"    },
};

function ScoreBar({ label, score }: { label: string; score: number }) {
  const color = score >= 70 ? "bg-emerald-500" : score >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-400 mb-1">
        <span>{label}</span>
        <span>{score.toFixed(1)}</span>
      </div>
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

export default function TrustProfilePage() {
  const params = useParams();
  const agentId = params.agentId as string;
  const router = useRouter();
  const [profile, setProfile] = useState<TrustProfile | null>(null);
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [skills, setSkills] = useState<SkillBinding[]>([]);
  const [connectors, setConnectors] = useState<SkillConnector[]>([]);
  const [loading, setLoading] = useState(true);
  const [recalc, setRecalc] = useState(false);
  const [error, setError] = useState("");

  const load = () => {
    Promise.all([
      getTrustProfile(agentId),
      getAgent(agentId),
      listAgentSkills(agentId),
      listSkillConnectors(),
    ])
      .then(([p, a, sk, cn]) => {
        setProfile(p);
        setAgent(a);
        setSkills(sk);
        setConnectors(cn);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }
    load();
  }, [agentId, router]);

  const handleRecalculate = async () => {
    setRecalc(true);
    try {
      const p = await recalculateTrust(agentId);
      setProfile(p);
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setRecalc(false);
    }
  };

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="animate-pulse text-gray-400">Loading trust profile…</div>
    </div>
  );

  const colors = TRUST_COLORS[profile?.trust_level ?? "provisional"];

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <button onClick={() => router.back()} className="text-xs text-gray-500 hover:text-gray-300 mb-4 flex items-center gap-1 transition">
          ← Back
        </button>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6 text-sm">{error}</div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          {/* Trust Profile Card */}
          <div className={`${colors.bg} border ${colors.border} rounded-xl p-6`}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h1 className="text-lg font-bold">{agent?.display_name ?? agentId.slice(0, 8)}</h1>
                <p className="text-xs text-gray-400 mt-0.5 font-mono">{agentId.slice(0, 16)}…</p>
              </div>
              <div className="text-right">
                <p className={`text-3xl font-bold ${colors.text}`}>{profile?.overall_score.toFixed(0)}</p>
                <p className={`text-xs font-semibold ${colors.text} uppercase`}>{profile?.trust_level}</p>
              </div>
            </div>

            {profile && (
              <div className="space-y-3">
                <ScoreBar label="Technical Trust" score={profile.technical_trust} />
                <ScoreBar label="Reliability Trust" score={profile.reliability_trust} />
                <ScoreBar label="Security Trust" score={profile.security_trust} />
              </div>
            )}

            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <div className="bg-gray-900/50 rounded-lg p-2">
                <p className="text-xs text-gray-500">Violations</p>
                <p className={`font-bold text-sm ${(profile?.tamper_violations ?? 0) > 0 ? "text-red-400" : "text-emerald-400"}`}>
                  {profile?.tamper_violations ?? 0}
                </p>
              </div>
              <div className="bg-gray-900/50 rounded-lg p-2">
                <p className="text-xs text-gray-500">Uptime</p>
                <p className="font-bold text-sm text-emerald-400">{profile?.uptime_pct.toFixed(1)}%</p>
              </div>
              <div className="bg-gray-900/50 rounded-lg p-2">
                <p className="text-xs text-gray-500">Heartbeats</p>
                <p className="font-bold text-sm text-blue-400">{profile?.heartbeat_checks ?? 0}</p>
              </div>
            </div>

            <button
              onClick={handleRecalculate}
              disabled={recalc}
              className="mt-4 w-full py-2 bg-gray-900/60 hover:bg-gray-800 disabled:opacity-50 border border-gray-700 rounded-lg text-xs font-medium transition"
            >
              {recalc ? "Recalculating…" : "Recalculate Score"}
            </button>

            <p className="text-xs text-gray-600 mt-2 text-center">
              Last calculated: {profile ? new Date(profile.calculated_at).toLocaleString() : "—"}
            </p>
          </div>

          {/* Skill Connectors */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-sm font-semibold mb-4">Bound Skills</h2>
            {skills.length === 0 ? (
              <div className="text-gray-500 text-xs py-4 text-center">
                <p className="mb-1">No skills bound</p>
                <p>Skills allow agents to use external tools like web search, email, etc.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {skills.map((s) => {
                  const connector = connectors.find((c) => c.connector_id === s.connector_id);
                  return (
                    <div key={s.binding_id} className="flex items-center justify-between border-b border-gray-800 pb-2">
                      <div>
                        <p className="text-xs font-medium">{connector?.name ?? s.connector_id.slice(0, 8)}</p>
                        <p className="text-xs text-gray-600">{connector?.category}</p>
                      </div>
                      <span className={`text-xs px-2 py-0.5 rounded-full ${s.enabled ? "bg-emerald-900/40 text-emerald-400" : "bg-gray-800 text-gray-500"}`}>
                        {s.enabled ? "enabled" : "disabled"}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-4 pt-4 border-t border-gray-800">
              <h3 className="text-xs font-semibold text-gray-400 mb-2">Available Connectors</h3>
              {connectors.length === 0 ? (
                <p className="text-xs text-gray-600">No public connectors available yet.</p>
              ) : (
                <div className="space-y-1.5">
                  {connectors.slice(0, 5).map((c) => (
                    <div key={c.connector_id} className="flex items-center justify-between text-xs">
                      <span className="text-gray-300">{c.name}</span>
                      <span className="text-gray-600">{c.category}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
