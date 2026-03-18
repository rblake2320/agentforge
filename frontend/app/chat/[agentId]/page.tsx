"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getAgent, chatWithAgent } from "@/lib/api";
import { AgentDetail } from "@/lib/types";
import Nav from "@/components/nav";

interface Message {
  id: string;
  role: "user" | "agent";
  content: string;
  runtime?: string;
  latency_ms?: number;
  timestamp: Date;
}

const RUNTIME_BADGE: Record<string, { label: string; cls: string }> = {
  nim: { label: "NIM", cls: "bg-green-900 text-green-400 border-green-800" },
  ollama: { label: "Ollama", cls: "bg-blue-900 text-blue-400 border-blue-800" },
  "21st": { label: "21st.dev", cls: "bg-purple-900 text-purple-400 border-purple-800" },
};

const TRUST_BADGE: Record<string, string> = {
  elite: "bg-yellow-900 text-yellow-400 border-yellow-800",
  verified: "bg-green-900 text-green-400 border-green-800",
  trusted: "bg-blue-900 text-blue-400 border-blue-800",
  provisional: "bg-orange-900 text-orange-400 border-orange-800",
  untrusted: "bg-red-900 text-red-400 border-red-800",
};

const TYPE_ICONS: Record<string, string> = {
  assistant: "🤖",
  worker: "⚙️",
  researcher: "🔬",
  analyst: "📊",
  coder: "💻",
  custom: "✨",
};

export default function ChatPage() {
  const params = useParams();
  const agentId = params.agentId as string;
  const router = useRouter();

  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    async function load() {
      try {
        const a = await getAgent(agentId);
        setAgent(a);
        if (!a.is_active) {
          setError("This agent is currently inactive and cannot accept messages.");
        }
      } catch {
        router.push("/dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [agentId, router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function sendMessage() {
    const text = input.trim();
    if (!text || sending || !agent?.is_active) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);
    setError("");

    // Build messages array for API (include history)
    const history = [...messages, userMsg].map((m) => ({
      role: m.role === "agent" ? "assistant" : "user",
      content: m.content,
    }));

    try {
      const res = await chatWithAgent(agentId, history, sessionId ?? undefined);
      setSessionId(res.session_id);
      const agentMsg: Message = {
        id: crypto.randomUUID(),
        role: "agent",
        content: res.content,
        runtime: res.runtime,
        latency_ms: res.latency_ms,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, agentMsg]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reach agent.");
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-400">
          <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          Loading agent…
        </div>
      </div>
    );
  }

  if (!agent) return null;

  const runtimeBadge = RUNTIME_BADGE[agent.preferred_runtime] ?? {
    label: agent.preferred_runtime,
    cls: "bg-gray-800 text-gray-400 border-gray-700",
  };
  const agentIcon = TYPE_ICONS[agent.agent_type] ?? "🤖";

  return (
    <div className="min-h-screen bg-gray-950 flex flex-col">
      <Nav />

      {/* Agent header */}
      <div className="border-b border-gray-800 bg-gray-900/60 backdrop-blur">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-4">
          <div className="w-11 h-11 bg-gray-800 rounded-xl flex items-center justify-center text-xl flex-shrink-0">
            {agentIcon}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-base font-semibold text-white truncate">{agent.display_name}</h1>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border ${runtimeBadge.cls}`}
              >
                {runtimeBadge.label}
              </span>
              <span
                className={`text-xs px-2 py-0.5 rounded-full border ${
                  agent.is_active
                    ? "bg-green-950 text-green-400 border-green-800"
                    : "bg-red-950 text-red-400 border-red-800"
                }`}
              >
                {agent.is_active ? "Active" : "Inactive"}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5 truncate">
              {agent.purpose || agent.did_uri}
            </p>
          </div>
          {agent.capabilities.length > 0 && (
            <div className="hidden sm:flex items-center gap-1.5 flex-shrink-0">
              {agent.capabilities.slice(0, 2).map((cap) => (
                <span
                  key={cap}
                  className="text-xs bg-gray-800 text-gray-400 px-2 py-0.5 rounded border border-gray-700"
                >
                  {cap}
                </span>
              ))}
              {agent.capabilities.length > 2 && (
                <span className="text-xs text-gray-600">+{agent.capabilities.length - 2}</span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
          {messages.length === 0 && !error && (
            <div className="text-center py-16">
              <div className="text-5xl mb-4">{agentIcon}</div>
              <h2 className="text-lg font-medium text-gray-300 mb-2">
                Chat with {agent.display_name}
              </h2>
              <p className="text-sm text-gray-500 max-w-sm mx-auto">
                {agent.purpose || "Send a message to start the conversation."}
              </p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-3 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}
            >
              {/* Avatar */}
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm flex-shrink-0 ${
                  msg.role === "user"
                    ? "bg-violet-700 text-white"
                    : "bg-gray-800 text-base"
                }`}
              >
                {msg.role === "user" ? "U" : agentIcon}
              </div>

              {/* Bubble */}
              <div className={`max-w-[78%] ${msg.role === "user" ? "items-end" : "items-start"} flex flex-col gap-1`}>
                <div
                  className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    msg.role === "user"
                      ? "bg-violet-600 text-white rounded-tr-sm"
                      : "bg-gray-800 text-gray-100 rounded-tl-sm"
                  }`}
                >
                  {msg.content}
                </div>
                <div className="flex items-center gap-2 px-1">
                  <span className="text-xs text-gray-600">
                    {msg.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                  {msg.runtime && (
                    <span className={`text-xs px-1.5 py-0.5 rounded border ${
                      RUNTIME_BADGE[msg.runtime]?.cls ?? "bg-gray-800 text-gray-500 border-gray-700"
                    }`}>
                      {RUNTIME_BADGE[msg.runtime]?.label ?? msg.runtime}
                    </span>
                  )}
                  {msg.latency_ms !== undefined && (
                    <span className="text-xs text-gray-600">{Math.round(msg.latency_ms)}ms</span>
                  )}
                </div>
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {sending && (
            <div className="flex gap-3 flex-row">
              <div className="w-8 h-8 rounded-full bg-gray-800 flex items-center justify-center text-base flex-shrink-0">
                {agentIcon}
              </div>
              <div className="bg-gray-800 px-4 py-3 rounded-2xl rounded-tl-sm flex items-center gap-1.5">
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <span className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Error bar */}
      {error && (
        <div className="border-t border-red-900 bg-red-950/60">
          <div className="max-w-3xl mx-auto px-4 py-2.5 flex items-center justify-between gap-4">
            <span className="text-sm text-red-400">{error}</span>
            {agent.is_active && (
              <button
                onClick={() => setError("")}
                className="text-xs text-red-500 hover:text-red-300 transition-colors flex-shrink-0"
              >
                Dismiss
              </button>
            )}
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-800 bg-gray-950">
        <div className="max-w-3xl mx-auto px-4 py-4">
          <div className="flex gap-3 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                agent.is_active
                  ? `Message ${agent.display_name}… (Enter to send, Shift+Enter for newline)`
                  : "Agent is inactive"
              }
              disabled={!agent.is_active || sending}
              rows={1}
              className="flex-1 bg-gray-900 border border-gray-700 focus:border-violet-600 text-gray-100
                placeholder-gray-600 rounded-xl px-4 py-3 text-sm resize-none outline-none transition-colors
                disabled:opacity-50 disabled:cursor-not-allowed max-h-40 overflow-y-auto"
              style={{ lineHeight: "1.5" }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 160) + "px";
              }}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || sending || !agent.is_active}
              className="bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed
                text-white rounded-xl px-4 py-3 transition-colors flex-shrink-0 flex items-center gap-2"
            >
              {sending ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M14.5 8L2 2l3 6-3 6 12.5-6z" />
                </svg>
              )}
              <span className="text-sm font-medium">{sending ? "Sending" : "Send"}</span>
            </button>
          </div>
          {sessionId && (
            <p className="text-xs text-gray-700 mt-2 text-center font-mono">
              session {sessionId.slice(0, 8)}…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
