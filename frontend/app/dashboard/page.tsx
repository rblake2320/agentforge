"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listAgents, getMe } from "../../lib/api";
import { Agent, User } from "../../lib/types";
import AgentCard from "../../components/agent-card";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      try {
        const [me, agentList] = await Promise.all([getMe(), listAgents()]);
        setUser(me as unknown as User);
        setAgents(agentList);
      } catch {
        router.push("/auth/login");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  function handleLogout() {
    localStorage.removeItem("access_token");
    router.push("/");
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="text-zinc-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950">
      {/* Nav */}
      <nav className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center text-black font-bold text-sm">
            AF
          </div>
          <span className="font-semibold text-zinc-100">AgentForge</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-zinc-400">{user?.email}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors"
          >
            Sign Out
          </button>
        </div>
      </nav>

      <main className="max-w-5xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">My Agents</h1>
            <p className="text-sm text-zinc-400 mt-1">
              {agents.length} agent{agents.length !== 1 ? "s" : ""} in your forge
            </p>
          </div>
          <Link
            href="/agents/create"
            className="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            + Birth Agent
          </Link>
        </div>

        {error && (
          <div className="bg-red-950 border border-red-800 text-red-400 text-sm px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {agents.length === 0 ? (
          <div className="border border-dashed border-zinc-700 rounded-xl p-12 text-center">
            <div className="text-4xl mb-4">🤖</div>
            <h3 className="text-lg font-medium text-zinc-300 mb-2">No agents yet</h3>
            <p className="text-sm text-zinc-500 mb-6">
              Birth your first AI agent to get a cryptographic identity, W3C DID, and Verifiable Credential.
            </p>
            <Link
              href="/agents/create"
              className="bg-green-600 hover:bg-green-500 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              Birth Your First Agent
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {agents.map((agent) => (
              <AgentCard key={agent.agent_id} agent={agent} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
