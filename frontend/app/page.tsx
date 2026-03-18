"use client";

import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gray-950 flex flex-col text-gray-100">
      {/* Nav */}
      <nav className="border-b border-gray-800 bg-gray-950/90 backdrop-blur sticky top-0 z-20">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-violet-600 rounded-lg flex items-center justify-center font-bold text-sm text-white">
              AF
            </div>
            <span className="font-bold text-gray-100 tracking-tight">AgentForge</span>
          </div>
          <div className="flex items-center gap-2">
            <Link
              href="/auth/login"
              className="px-4 py-2 text-sm text-gray-400 hover:text-gray-100 transition-colors"
            >
              Login
            </Link>
            <Link
              href="/auth/register"
              className="px-4 py-2 text-sm bg-violet-600 hover:bg-violet-500 text-white rounded-lg font-medium transition-colors"
            >
              Register
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-28 text-center relative overflow-hidden">
        {/* Background glow */}
        <div className="absolute inset-0 pointer-events-none">
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-violet-900/20 rounded-full blur-3xl" />
        </div>

        <div className="relative z-10 max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-violet-950 border border-violet-800 text-violet-300 text-xs px-4 py-1.5 rounded-full mb-8">
            <span className="w-1.5 h-1.5 bg-violet-400 rounded-full animate-pulse" />
            W3C DID Standard · Ed25519 · XChaCha20-Poly1305 Vault
          </div>

          <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-100 leading-tight mb-6">
            AgentForge —{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-violet-600">
              Forge Permanent
            </span>
            <br />
            Cryptographic Identities
            <br />
            for AI Agents
          </h1>

          <p className="text-lg md:text-xl text-gray-400 max-w-2xl mx-auto mb-4">
            Birth agents with immutable W3C DIDs backed by Ed25519 keypairs. License clones
            cryptographically. Agents persist across devices, sessions, and runtimes.
          </p>
          <p className="text-sm text-gray-500 max-w-xl mx-auto mb-12">
            Every agent gets a verifiable credential, a tamper-detection Merkle chain, and a
            patent-pending clone licensing mechanism — all under your control.
          </p>

          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/auth/register"
              className="px-8 py-3.5 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-semibold text-base transition-colors shadow-lg shadow-violet-900/30"
            >
              Get Started
            </Link>
            <Link
              href="/docs"
              className="px-8 py-3.5 border border-gray-700 hover:border-violet-600 hover:text-violet-300 text-gray-300 rounded-xl font-semibold text-base transition-colors"
            >
              View Docs
            </Link>
          </div>
        </div>
      </section>

      {/* Feature columns */}
      <section className="border-t border-gray-800 bg-gray-900/40 px-6 py-20">
        <div className="max-w-5xl mx-auto">
          <h2 className="text-center text-2xl font-bold text-gray-100 mb-3">
            Enterprise-grade identity infrastructure
          </h2>
          <p className="text-center text-gray-500 text-sm mb-12">
            Built on open standards. Owned by you.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {FEATURES.map((f) => (
              <div
                key={f.title}
                className="bg-gray-900 border border-gray-800 hover:border-violet-800/60 rounded-2xl p-7 transition-colors group"
              >
                <div className="w-12 h-12 bg-violet-950 border border-violet-800 rounded-xl flex items-center justify-center text-2xl mb-5 group-hover:border-violet-600 transition-colors">
                  {f.icon}
                </div>
                <h3 className="font-semibold text-gray-100 text-base mb-2">{f.title}</h3>
                <p className="text-sm text-gray-400 leading-relaxed">{f.desc}</p>
                <div className="mt-5 flex flex-wrap gap-1.5">
                  {f.tags.map((t) => (
                    <span
                      key={t}
                      className="text-xs bg-violet-950/60 border border-violet-900 text-violet-400 px-2 py-0.5 rounded-full"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Stats row */}
      <section className="border-t border-gray-800 px-6 py-14">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6">
          {STATS.map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-3xl font-bold text-violet-400 mb-1">{s.value}</p>
              <p className="text-sm text-gray-500">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA Banner */}
      <section className="border-t border-gray-800 bg-gradient-to-r from-violet-950/60 via-gray-900 to-violet-950/60 px-6 py-16">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-2xl font-bold text-gray-100 mb-3">
            Ready to forge your first agent?
          </h2>
          <p className="text-gray-400 text-sm mb-8">
            Create an account in seconds. No credit card required for the free tier.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/auth/register"
              className="px-8 py-3 bg-violet-600 hover:bg-violet-500 text-white rounded-xl font-semibold transition-colors"
            >
              Get Started — Free
            </Link>
            <Link
              href="/docs"
              className="px-8 py-3 border border-gray-700 hover:border-gray-500 text-gray-300 rounded-xl font-semibold transition-colors"
            >
              View Docs
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-gray-800 px-6 py-8">
        <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-violet-600 rounded flex items-center justify-center text-xs font-bold text-white">
              AF
            </div>
            <span className="text-sm text-gray-400">AgentForge · AI Agent Identity Platform</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-gray-500">
            <Link
              href="https://github.com/rblake2320/agentforge"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-300 transition-colors flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
                />
              </svg>
              GitHub
            </Link>
            <Link href="/docs" className="hover:text-gray-300 transition-colors">
              Docs
            </Link>
            <Link href="/auth/login" className="hover:text-gray-300 transition-colors">
              Login
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}

const FEATURES = [
  {
    icon: "🔐",
    title: "Cryptographic Identity",
    desc: "Each agent receives a permanent Ed25519 keypair and a W3C DID Document — a decentralized identifier that is cryptographically verifiable and owned by you, not any platform.",
    tags: ["Ed25519", "W3C DID", "Verifiable Credentials"],
  },
  {
    icon: "🔒",
    title: "User-Controlled Wallet",
    desc: "Private keys are encrypted with XChaCha20-Poly1305 and stored in your personal vault. Only you can decrypt. AgentForge never holds your keys in plaintext.",
    tags: ["XChaCha20-Poly1305", "Zero-Knowledge", "Self-Custody"],
  },
  {
    icon: "🏪",
    title: "Clone Licensing Marketplace",
    desc: "List trained agents on the marketplace. Buyers receive a cryptographically signed clone with a unique license key. Revenue flows directly to you. Patent-pending.",
    tags: ["Patent-Pending", "Signed Clones", "License Keys"],
  },
];

const STATS = [
  { value: "87", label: "Tests passing" },
  { value: "6", label: "Phases complete" },
  { value: "RTX 5090", label: "Powered by" },
  { value: "Ed25519", label: "Key algorithm" },
];
