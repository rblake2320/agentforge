"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { browseListings, purchaseListing } from "@/lib/api";
import type { Listing } from "@/lib/types";
import Nav from "@/components/nav";

const CATEGORIES = ["all", "assistant", "code", "research", "data", "creative", "utility"];

const LICENSE_LABELS: Record<string, string> = {
  perpetual: "Perpetual",
  subscription: "30-day",
  per_use: "Pay/use",
};

function ListingCard({
  listing,
  onPurchase,
  purchasing,
}: {
  listing: Listing;
  onPurchase: (id: string) => void;
  purchasing: string | null;
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-3 hover:border-violet-700 transition">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-semibold text-sm">{listing.title}</h3>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full mt-1 inline-block">
            {listing.category}
          </span>
        </div>
        <div className="text-right">
          <div className="text-lg font-bold text-violet-400">
            {listing.price_cents === 0 ? "Free" : `$${(listing.price_cents / 100).toFixed(2)}`}
          </div>
          <div className="text-xs text-gray-500">{LICENSE_LABELS[listing.license_type]}</div>
        </div>
      </div>

      <p className="text-xs text-gray-400 line-clamp-2">{listing.description || "No description."}</p>

      <div className="flex flex-wrap gap-1">
        {listing.tags.slice(0, 4).map((t) => (
          <span key={t} className="text-xs bg-gray-800 text-gray-300 px-2 py-0.5 rounded-full">
            {t}
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between mt-auto">
        <span className="text-xs text-gray-500">
          {listing.total_sales} sold · {listing.max_clones - listing.total_sales} left
        </span>
        <button
          onClick={() => onPurchase(listing.listing_id)}
          disabled={purchasing === listing.listing_id || listing.total_sales >= listing.max_clones}
          className="px-3 py-1.5 bg-violet-600 hover:bg-violet-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg text-xs font-medium transition"
        >
          {purchasing === listing.listing_id ? "Processing…" : "Purchase"}
        </button>
      </div>
    </div>
  );
}

export default function MarketplacePage() {
  const router = useRouter();
  const [listings, setListings] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [purchasing, setPurchasing] = useState<string | null>(null);

  const fetchListings = () => {
    setLoading(true);
    setError("");
    browseListings({
      category: category === "all" ? undefined : category,
      search: search || undefined,
    })
      .then(({ listings: l, total: t }) => { setListings(l); setTotal(t); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { router.push("/auth/login"); return; }
    fetchListings();
  }, [category]);

  const handlePurchase = async (id: string) => {
    setPurchasing(id);
    setError("");
    try {
      const result = await purchaseListing(id);
      setSuccess(`License purchased! Key: ${result.license_key.slice(0, 20)}…`);
      fetchListings();
    } catch (e: unknown) {
      setError((e as Error).message);
    } finally {
      setPurchasing(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Nav />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold">Agent Marketplace</h1>
            <p className="text-gray-400 text-sm mt-1">{total} agents available</p>
          </div>
          <button
            onClick={() => router.push("/marketplace/create")}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium transition"
          >
            + List Agent
          </button>
        </div>

        {/* Search + Filter */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <input
            type="text"
            placeholder="Search agents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && fetchListings()}
            className="flex-1 bg-gray-900 border border-gray-700 rounded-lg px-4 py-2 text-sm focus:outline-none focus:border-violet-500"
          />
          <button
            onClick={fetchListings}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-sm transition"
          >
            Search
          </button>
        </div>

        <div className="flex gap-2 flex-wrap mb-6">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => setCategory(c)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition ${
                category === c
                  ? "bg-violet-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {c}
            </button>
          ))}
        </div>

        {success && (
          <div className="bg-emerald-900/30 border border-emerald-700 text-emerald-300 rounded-lg p-4 mb-4 text-sm">
            ✓ {success}
          </div>
        )}
        {error && (
          <div className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-4 text-sm">{error}</div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-5 h-48 animate-pulse" />
            ))}
          </div>
        ) : listings.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <p className="text-lg mb-2">No listings found</p>
            <p className="text-sm">Be the first to list an agent!</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {listings.map((l) => (
              <ListingCard key={l.listing_id} listing={l} onPurchase={handlePurchase} purchasing={purchasing} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
