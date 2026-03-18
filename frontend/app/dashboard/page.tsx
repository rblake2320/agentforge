"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listAgents, getMe, getWallet } from "@/lib/api";
import { Agent, User, Wallet } from "@/lib/types";
import AgentCard from "@/components/agent-card";
import Nav from "@/components/nav";

const QUICK_ACTIONS = [
  {
    href: "/agents/create",
    icon: "⚡",
    label: "Birth Agent",
    desc: "Create a new AI agent with cryptographic identity",
    accent: "border-violet-800 hover:border-violet-600",
    iconBg: "bg-violet-950 text-violet-400",
  },
  {
    href: "/marketplace",
    icon: "🛒",
    label: "Browse Marketplace",
    desc: "Discover and purchase AI agents from the community",
    accent: "border-gray-800 hover:border-gray-600",
    iconBg: "bg-gray-900 text-gray-300",
  },
  {
    href: "/devices",
    icon: "📱",
    label: "Manage Devices",
    desc: "Register devices for portable agent execution",
    accent: "border-gray-800 hover:border-gray-600",
    iconBg: "bg-gray-900 text-gray-300",
  },
  {
    href: "/marketplace/revenue",
    icon: "💰",
    label: "Seller Revenue",
    desc: "Track your marketplace earnings and license activity",
    accent: "border-gray-800 hover:border-gray-600",
    iconBg: "bg-gray-900 text-gray-300",
  },
];

interface ChecklistItem {
  label: string;
  done: boolean;
  href: string;
  action: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [wallet, setWallet] = useState<Wallet | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [me, agentList, walletData] = await Promise.all([
          getMe(),
          listAgents(),
          getWallet().catch(() => null),
        ]);
        setUser(me as unknown as User);
        setAgents(agentList);
        setWallet(walletData);
      } catch {
        router.push("/auth/login");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  const activeAgents = agents.filter((a) => a.is_active).length;
  const storedKeys = wallet?.keys?.filter((k) => !k.revoked_at).length ?? 0;

  const checklist: ChecklistItem[] = [
    {
      label: "Create your first agent",
      done: agents.length > 0,
      href: "/agents/create",
      action: "Birth Agent →",
    },
    {
      label: "Store a private key in your wallet",
      done: storedKeys > 0,
      href: "/wallet",
      action: "Open Wallet →",
    },
    {
      label: "List an agent on the marketplace",
      done: false,
      href: "/marketplace",
      action: "Go to Marketplace →",
    },
  ];

  const completedSteps = checklist.filter((c) => c.done).length;
  const allDone = completedSteps === checklist.length;

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-400">
          <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          Loading command center…
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950">
      <Nav />

      <main className="max-w-6xl mx-auto px-4 py-10 space-y-10">
        {/* Welcome header */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-500 mb-1">Welcome back</p>
            <h1 className="text-3xl font-bold text-white">
              {user?.name ?? user?.email ?? "Agent Commander"}
            </h1>
            <p className="text-sm text-gray-500 mt-1">{user?.email}</p>
          </div>
          <Link
            href="/agents/create"
            className="bg-violet-600 hover:bg-violet-500 text-white px-5 py-2.5 rounded-lg text-sm font-semibold transition-colors flex items-center gap-2"
          >
            <span>⚡</span> Birth Agent
          </Link>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total Agents", value: agents.length, icon: "🤖", color: "text-violet-400" },
            { label: "Active Agents", value: activeAgents, icon: "✅", color: "text-green-400" },
            { label: "Stored Keys", value: storedKeys, icon: "🔑", color: "text-yellow-400" },
            {
              label: "Trust Scores",
              value: agents.filter((a) => a.key_fingerprint).length,
              icon: "🛡️",
              color: "text-blue-400",
            },
          ].map((stat) => (
            <div
              key={stat.label}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex items-center gap-4"
            >
              <div className="text-2xl">{stat.icon}</div>
              <div>
                <div className={`text-2xl font-bold ${stat.color}`}>{stat.value}</div>
                <div className="text-xs text-gray-500 mt-0.5">{stat.label}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Recent agents */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Recent Agents</h2>
            {agents.length > 3 && (
              <Link href="/agents" className="text-sm text-violet-400 hover:text-violet-300 transition-colors">
                View all {agents.length} →
              </Link>
            )}
          </div>

          {agents.length === 0 ? (
            <div className="border border-dashed border-gray-800 rounded-xl p-12 text-center">
              <div className="text-4xl mb-3">🤖</div>
              <h3 className="text-base font-medium text-gray-300 mb-2">No agents yet</h3>
              <p className="text-sm text-gray-500 mb-6 max-w-sm mx-auto">
                Birth your first AI agent to get a cryptographic identity, W3C DID, and Verifiable Credential.
              </p>
              <Link
                href="/agents/create"
                className="bg-violet-600 hover:bg-violet-500 text-white px-6 py-2.5 rounded-lg text-sm font-semibold transition-colors"
              >
                Birth Your First Agent
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.slice(0, 3).map((agent) => (
                <AgentCard key={agent.agent_id} agent={agent} />
              ))}
            </div>
          )}
        </section>

        {/* Quick actions */}
        <section>
          <h2 className="text-lg font-semibold text-white mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {QUICK_ACTIONS.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className={`bg-gray-900 border rounded-xl p-5 transition-colors group ${action.accent}`}
              >
                <div className={`w-10 h-10 rounded-lg flex items-center justify-center text-xl mb-3 ${action.iconBg}`}>
                  {action.icon}
                </div>
                <div className="font-semibold text-white text-sm mb-1">{action.label}</div>
                <div className="text-xs text-gray-500 leading-relaxed">{action.desc}</div>
              </Link>
            ))}
          </div>
        </section>

        {/* Getting started checklist */}
        {!allDone && (
          <section>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Getting Started</h2>
              <span className="text-xs text-gray-500 bg-gray-900 border border-gray-800 px-2.5 py-1 rounded-full">
                {completedSteps} / {checklist.length} complete
              </span>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              {checklist.map((item, i) => (
                <div
                  key={item.label}
                  className={`flex items-center gap-4 px-6 py-4 ${
                    i < checklist.length - 1 ? "border-b border-gray-800" : ""
                  }`}
                >
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 border-2 transition-colors ${
                      item.done
                        ? "bg-violet-600 border-violet-600 text-white"
                        : "border-gray-700 bg-gray-950"
                    }`}
                  >
                    {item.done && (
                      <svg className="w-3.5 h-3.5" viewBox="0 0 14 14" fill="none">
                        <path d="M2 7l4 4 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <span
                      className={`text-sm ${
                        item.done ? "line-through text-gray-600" : "text-gray-300"
                      }`}
                    >
                      {item.label}
                    </span>
                  </div>
                  {!item.done && (
                    <Link
                      href={item.href}
                      className="text-xs text-violet-400 hover:text-violet-300 transition-colors whitespace-nowrap"
                    >
                      {item.action}
                    </Link>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
