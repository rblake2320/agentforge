"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSellerRevenue, browseListings } from "@/lib/api";
import type { SellerRevenue, Listing } from "@/lib/types";
import Nav from "@/components/nav";

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-violet-400">{value}</p>
      {sub && <p className="text-xs text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}

export default function RevenueDashboard() {
  const router = useRouter();
  const [revenue, setRevenue] = useState<SellerRevenue | null>(null);
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }
    Promise.all([getSellerRevenue(), browseListings()])
      .then(([rev, { listings: l }]) => { setRevenue(rev); setListings(l); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [router]);

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="animate-pulse text-gray-400">Loading revenue data…</div>
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-5xl mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-6">Revenue Dashboard</h1>

        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-6 text-sm">{error}</div>
        )}

        {revenue && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <StatCard label="Gross Revenue" value={`$${revenue.total_gross_usd.toFixed(2)}`} sub="all time" />
            <StatCard label="Net Revenue" value={`$${revenue.total_net_usd.toFixed(2)}`} sub="after 20% fee" />
            <StatCard label="Total Licenses" value={String(revenue.total_licenses)} sub={`${revenue.active_licenses} active`} />
            <StatCard label="Listings" value={String(revenue.listings)} />
          </div>
        )}

        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="text-sm font-semibold text-gray-300 mb-4">Your Listings</h2>
          {listings.length === 0 ? (
            <p className="text-gray-500 text-sm">No listings yet. <button onClick={() => router.push("/marketplace/create")} className="text-violet-400 underline">Create one.</button></p>
          ) : (
            <div className="space-y-3">
              {listings.map((l) => (
                <div key={l.listing_id} className="flex items-center justify-between border-b border-gray-800 pb-3">
                  <div>
                    <p className="text-sm font-medium">{l.title}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{l.category} · {l.license_type}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-violet-400 font-semibold">
                      {l.price_cents === 0 ? "Free" : `$${(l.price_cents / 100).toFixed(2)}`}
                    </p>
                    <p className="text-xs text-gray-500">{l.total_sales}/{l.max_clones} sold</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="mt-6 bg-gray-900/50 border border-gray-700 rounded-xl p-4 text-xs text-gray-400">
          <p className="font-semibold text-gray-300 mb-1">Platform Fee Structure</p>
          <p>20% of each transaction is retained by AgentForge. Elite-tier agents (trust score 90+) qualify for a 15% reduced fee (coming soon).</p>
        </div>
      </main>
    </div>
  );
}
