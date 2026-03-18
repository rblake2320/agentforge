import Link from "next/link";
import { Agent } from "../lib/types";

const RUNTIME_BADGES: Record<string, { label: string; color: string }> = {
  nim: { label: "NIM", color: "bg-green-900 text-green-400 border-green-800" },
  ollama: { label: "Ollama", color: "bg-blue-900 text-blue-400 border-blue-800" },
  "21st": { label: "21st.dev", color: "bg-purple-900 text-purple-400 border-purple-800" },
};

const TYPE_ICONS: Record<string, string> = {
  assistant: "🤖",
  worker: "⚙️",
  researcher: "🔬",
  analyst: "📊",
  coder: "💻",
  custom: "✨",
};

interface Props {
  agent: Agent;
}

export default function AgentCard({ agent }: Props) {
  const runtime = RUNTIME_BADGES[agent.preferred_runtime] ?? { label: agent.preferred_runtime, color: "bg-zinc-800 text-zinc-400 border-zinc-700" };
  const icon = TYPE_ICONS[agent.agent_type] ?? "🤖";

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 hover:border-zinc-600 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-zinc-800 rounded-lg flex items-center justify-center text-lg">
            {icon}
          </div>
          <div>
            <h3 className="font-medium text-zinc-100 text-sm">{agent.display_name}</h3>
            <p className="text-xs text-zinc-500 capitalize">{agent.agent_type}</p>
          </div>
        </div>
        <div className={`text-xs px-2 py-0.5 rounded-full border ${runtime.color}`}>
          {runtime.label}
        </div>
      </div>

      {agent.purpose && (
        <p className="text-xs text-zinc-400 mb-3 line-clamp-2">{agent.purpose}</p>
      )}

      {agent.capabilities.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-3">
          {agent.capabilities.slice(0, 3).map((cap) => (
            <span key={cap} className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
              {cap}
            </span>
          ))}
          {agent.capabilities.length > 3 && (
            <span className="text-xs text-zinc-600">+{agent.capabilities.length - 3}</span>
          )}
        </div>
      )}

      <div className="border-t border-zinc-800 pt-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full ${agent.is_active ? "bg-green-400" : "bg-zinc-600"}`} />
            <span className="text-xs text-zinc-500 font-mono">{agent.key_fingerprint.slice(0, 12)}...</span>
          </div>
          <Link
            href={`/agents/${agent.agent_id}`}
            className="text-xs text-green-400 hover:text-green-300 transition-colors"
          >
            View →
          </Link>
        </div>
      </div>
    </div>
  );
}
