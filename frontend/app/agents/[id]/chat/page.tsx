"use client";

import { useEffect, useState, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAgent, chatWithAgent } from "@/lib/api";
import type { AgentDetail } from "@/lib/types";
import Nav from "@/components/nav";

interface Message {
  role: "user" | "assistant";
  content: string;
  sig_id?: string | null;
  runtime?: string;
  latency_ms?: number;
}

export default function ChatPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;

  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);
  const [agentLoading, setAgentLoading] = useState(true);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }

    getAgent(agentId)
      .then(setAgent)
      .catch(() => router.push("/dashboard"))
      .finally(() => setAgentLoading(false));
  }, [agentId, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const history = [...messages, userMsg].map((m) => ({ role: m.role, content: m.content }));
      const res = await chatWithAgent(agentId, history, sessionId);
      setSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: res.content,
          sig_id: res.sig_id,
          runtime: res.runtime,
          latency_ms: res.latency_ms,
        },
      ]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Chat failed";
      const isRuntimeError = msg.includes("runtimes") || msg.includes("unavailable") || msg.includes("503");
      const displayMsg = isRuntimeError
        ? "⚠️ No LLM runtime available.\n\nTo enable chat:\n• Start NVIDIA NIM: see NVIDIA_SETUP.md\n• Or ensure Ollama is running with `ollama serve` and has llama3.1:8b or qwen2.5:7b loaded\n\nThe agent identity, wallet, and marketplace features work without a runtime."
        : `⚠️ Error: ${msg}`;
      setMessages((prev) => [...prev, { role: "assistant", content: displayMsg }]);
    } finally {
      setLoading(false);
    }
  };

  if (agentLoading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="animate-pulse text-gray-400">Loading agent…</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <Nav />
      <div className="flex-1 flex flex-col max-w-3xl mx-auto w-full px-4 pb-4">
        {/* Header */}
        <div className="flex items-center justify-between py-4 border-b border-gray-800">
          <div className="flex items-center gap-3">
            <button onClick={() => router.back()} className="text-gray-400 hover:text-white text-sm">← Back</button>
            <div>
              <h1 className="font-semibold">{agent?.display_name ?? agentId}</h1>
              <p className="text-xs text-gray-500">
                {agent?.preferred_runtime ?? "nim"} runtime
                {sessionId && <span className="ml-2 font-mono">session {sessionId.slice(0, 8)}…</span>}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${agent?.is_active ? "bg-emerald-400 animate-pulse" : "bg-gray-600"}`} />
            <span className="text-xs text-gray-500">{agent?.is_active ? "active" : "offline"}</span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-20 text-gray-600">
              <p className="text-4xl mb-3">💬</p>
              <p className="text-sm">Start a conversation with {agent?.display_name ?? "this agent"}.</p>
              <p className="text-xs mt-1">Messages are signed with the agent&apos;s Ed25519 key.</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === "user"
                  ? "bg-violet-700 text-white"
                  : "bg-gray-800 text-gray-100"
              }`}>
                <p className="whitespace-pre-wrap">{msg.content}</p>
                {msg.role === "assistant" && (msg.sig_id || msg.runtime) && (
                  <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-700 text-xs text-gray-500">
                    {msg.runtime && <span>{msg.runtime}</span>}
                    {msg.sig_id && <span className="font-mono">sig {msg.sig_id.slice(0, 8)}…</span>}
                    {msg.latency_ms && <span>{msg.latency_ms}ms</span>}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-gray-800 rounded-2xl px-4 py-3 text-sm text-gray-400">
                <span className="animate-pulse">Thinking…</span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-800 pt-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
              placeholder="Message the agent…"
              disabled={loading}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:border-violet-500 disabled:opacity-50"
            />
            <button
              onClick={sendMessage}
              disabled={loading || !input.trim()}
              className="px-4 py-2.5 bg-violet-600 hover:bg-violet-700 disabled:opacity-40 rounded-xl text-sm font-medium transition"
            >
              Send
            </button>
          </div>
          <p className="text-xs text-gray-600 mt-2 text-center">
            Responses are cryptographically signed with the agent&apos;s identity key
          </p>
        </div>
      </div>
    </div>
  );
}
