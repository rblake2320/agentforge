"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { listDevices, registerDevice, deregisterDevice } from "@/lib/api";
import type { Device } from "@/lib/types";
import Nav from "@/components/nav";

function timeAgo(ts: string) {
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

const DEVICE_ICONS: Record<string, string> = {
  desktop: "🖥️",
  laptop: "💻",
  mobile: "📱",
  tablet: "📱",
  server: "🖧",
};

export default function DevicesPage() {
  const router = useRouter();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [registering, setRegistering] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ device_name: "", device_type: "desktop" });

  const loadDevices = () =>
    listDevices()
      .then(setDevices)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }
    loadDevices();
  }, [router]);

  const handleRegister = async () => {
    setRegistering(true);
    setError("");
    try {
      // In production: use Web Crypto API to generate real Ed25519 key
      // For demo: generate a random 32-byte "public key"
      const randomBytes = crypto.getRandomValues(new Uint8Array(32));
      const publicKeyHex = Array.from(randomBytes).map(b => b.toString(16).padStart(2, "0")).join("");
      const fingerprint = Array.from(randomBytes.slice(0, 16)).map(b => b.toString(16).padStart(2, "0")).join("");

      await registerDevice({
        device_name: form.device_name || navigator.platform || "My Device",
        device_type: form.device_type,
        device_fingerprint: fingerprint,
        public_key_hex: publicKeyHex,
      });
      setShowForm(false);
      setForm({ device_name: "", device_type: "desktop" });
      loadDevices();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setRegistering(false);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Remove this device?")) return;
    try {
      await deregisterDevice(id);
      setDevices((d) => d.filter((x) => x.device_id !== id));
    } catch (e: unknown) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Devices</h1>
            <p className="text-gray-400 text-sm mt-1">Trusted devices for cross-device agent portability</p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium transition"
          >
            + Register Device
          </button>
        </div>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-4 text-sm">{error}</div>
        )}

        {showForm && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold mb-4">Register This Device</h2>
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label className="text-xs text-gray-400 block mb-1">Device Name</label>
                <input
                  type="text"
                  placeholder="My Laptop"
                  value={form.device_name}
                  onChange={(e) => setForm({ ...form, device_name: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 block mb-1">Device Type</label>
                <select
                  value={form.device_type}
                  onChange={(e) => setForm({ ...form, device_type: e.target.value })}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-violet-500"
                >
                  {["desktop", "laptop", "mobile", "tablet", "server"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setShowForm(false)} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition">
                Cancel
              </button>
              <button onClick={handleRegister} disabled={registering} className="px-4 py-2 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-700 rounded-lg text-sm font-medium transition">
                {registering ? "Registering…" : "Register"}
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="animate-pulse text-gray-500 text-sm">Loading devices…</div>
        ) : devices.length === 0 ? (
          <div className="text-center py-16 text-gray-500">
            <p className="text-4xl mb-3">🖥️</p>
            <p className="text-lg mb-1">No devices registered</p>
            <p className="text-sm">Register this device to enable cross-device agent portability.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {devices.map((d) => (
              <div key={d.device_id} className="bg-gray-900 border border-gray-800 rounded-xl p-4 flex items-center gap-4">
                <span className="text-2xl">{DEVICE_ICONS[d.device_type] ?? "💻"}</span>
                <div className="flex-1">
                  <p className="font-medium text-sm">{d.device_name}</p>
                  <p className="text-xs text-gray-500 mt-0.5 font-mono">{d.device_fingerprint.slice(0, 16)}…</p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-gray-400">{d.device_type}</p>
                  <p className="text-xs text-gray-600 mt-0.5">seen {timeAgo(d.last_seen)}</p>
                </div>
                <button
                  onClick={() => handleDelete(d.device_id)}
                  className="text-xs text-red-500 hover:text-red-400 transition px-2 py-1"
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="mt-8 bg-gray-900/40 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-2">Session Handoff</h2>
          <p className="text-xs text-gray-400 mb-3">
            Transfer agent context between registered devices using encrypted one-time tokens.
          </p>
          <p className="text-xs text-gray-600">
            API: POST /api/v1/portability/handoff → token → POST /api/v1/portability/handoff/accept
          </p>
        </div>
      </main>
    </div>
  );
}
