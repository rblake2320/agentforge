import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-zinc-950 flex flex-col">
      {/* Nav */}
      <nav className="border-b border-zinc-800 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-green-500 rounded-lg flex items-center justify-center text-black font-bold text-sm">
            AF
          </div>
          <span className="font-semibold text-zinc-100">AgentForge</span>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/auth/login" className="text-sm text-zinc-400 hover:text-zinc-100 transition-colors">
            Sign In
          </Link>
          <Link
            href="/auth/register"
            className="text-sm bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded-lg transition-colors"
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <section className="flex-1 flex flex-col items-center justify-center px-6 py-24 text-center">
        <div className="inline-flex items-center gap-2 bg-green-950 border border-green-800 text-green-400 text-xs px-3 py-1 rounded-full mb-6">
          <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
          W3C DID Standard · Ed25519 · Verifiable Credentials
        </div>
        <h1 className="text-5xl md:text-6xl font-bold text-zinc-100 max-w-3xl leading-tight mb-6">
          Cryptographic Identities for{" "}
          <span className="text-green-400">AI Agents</span>
        </h1>
        <p className="text-lg text-zinc-400 max-w-2xl mb-10">
          Birth agents with permanent W3C DIDs. Store private keys in your wallet.
          License agents to companies. Detect tampering with Merkle chains.
          Agents follow you across devices.
        </p>
        <div className="flex flex-col sm:flex-row gap-4">
          <Link
            href="/auth/register"
            className="bg-green-600 hover:bg-green-500 text-white px-8 py-3 rounded-lg font-medium transition-colors"
          >
            Birth Your First Agent
          </Link>
          <Link
            href="/docs"
            className="border border-zinc-700 hover:border-zinc-500 text-zinc-300 px-8 py-3 rounded-lg font-medium transition-colors"
          >
            Read the Docs
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="border-t border-zinc-800 px-6 py-16">
        <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-8">
          {features.map((f) => (
            <div key={f.title} className="bg-zinc-900 rounded-xl p-6 border border-zinc-800">
              <div className="text-2xl mb-3">{f.icon}</div>
              <h3 className="font-semibold text-zinc-100 mb-2">{f.title}</h3>
              <p className="text-sm text-zinc-400">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

const features = [
  {
    icon: "🔐",
    title: "Cryptographic Identity",
    desc: "Each agent gets an Ed25519 keypair and a W3C DID Document. Private keys stay in your encrypted wallet.",
  },
  {
    icon: "🔗",
    title: "Tamper Detection",
    desc: "Every session is chained with Merkle tree proofs. Detect any modification to agent behavior instantly.",
  },
  {
    icon: "🏪",
    title: "Licensing Marketplace",
    desc: "List your trained agents. Buyers get cryptographically signed clones. You earn from every use.",
  },
];
