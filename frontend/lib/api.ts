import type { Agent, AgentDetail } from "./types";

const BASE = "/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (auth) {
    const token = getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail ?? res.statusText);
  }
  return res.json();
}

// Auth
export const register = (email: string, password: string, name: string) =>
  request<{ id: string; email: string }>("POST", "/auth/register", { email, password, name }, false);

export const login = (email: string, password: string) =>
  request<{ access_token: string; expires_in: number }>("POST", "/auth/login", { email, password }, false);

export const getMe = () => request<{ id: string; email: string; name: string }>("GET", "/auth/me");

// Agents
export const createAgent = (data: {
  display_name: string;
  agent_type?: string;
  purpose?: string;
  capabilities?: string[];
  preferred_runtime?: string;
  is_public?: boolean;
}) => request<{ agent: Agent; private_key_hex: string; warning: string }>("POST", "/agents/", data);

export const listAgents = () => request<Agent[]>("GET", "/agents/");

export const getAgent = (id: string) => request<AgentDetail>("GET", `/agents/${id}`);

export const getCertificate = (id: string) => request<Record<string, unknown>>("GET", `/agents/${id}/certificate`);

// Wallet
export const getWallet = () => request<import("./types").Wallet>("GET", "/wallet/");
export const createWallet = (passphrase: string) =>
  request<import("./types").Wallet>("POST", "/wallet/", { passphrase });
export const storeKey = (agentId: string, privateKeyHex: string, passphrase: string) =>
  request("POST", "/wallet/keys", { agent_id: agentId, private_key_hex: privateKeyHex, passphrase });
export const rotateKey = (agentId: string, newPrivateKeyHex: string, passphrase: string) =>
  request("POST", `/wallet/keys/rotate/${agentId}`, { private_key_hex: newPrivateKeyHex, passphrase });

// Marketplace
export const browseListings = (params?: { category?: string; search?: string; max_price?: number; offset?: number }) => {
  const qs = new URLSearchParams();
  if (params?.category) qs.set("category", params.category);
  if (params?.search) qs.set("search", params.search);
  if (params?.max_price) qs.set("max_price_cents", String(params.max_price * 100));
  return request<{ listings: import("./types").Listing[]; total: number }>("GET", `/marketplace/listings?${qs}`);
};
export const createListing = (data: {
  agent_id: string; title: string; description: string; price_cents: number;
  license_type: string; max_clones?: number; category?: string; tags?: string[];
}) => request<import("./types").Listing>("POST", "/marketplace/listings", data);
export const purchaseListing = (listingId: string) =>
  request<{ license: import("./types").License; clone_agent_id: string; license_key: string }>("POST", `/marketplace/listings/${listingId}/purchase`);
export const getMyLicenses = () => request<import("./types").License[]>("GET", "/marketplace/licenses");
export const getSellerRevenue = () => request<import("./types").SellerRevenue>("GET", "/marketplace/revenue");

// Portability - Devices
export const listDevices = () => request<import("./types").Device[]>("GET", "/portability/devices");
export const registerDevice = (data: { device_name: string; device_type: string; device_fingerprint: string; public_key_hex: string }) =>
  request<import("./types").Device>("POST", "/portability/devices", data);
export const deregisterDevice = (deviceId: string) =>
  request("DELETE", `/portability/devices/${deviceId}`);

// Portability - Memory
export const listMemories = (agentId: string, layer?: string) => {
  const qs = layer ? `?layer=${layer}` : "";
  return request<import("./types").MemoryEntry[]>("GET", `/portability/memory/${agentId}${qs}`);
};

// Chat
export const chatWithAgent = (
  agentId: string,
  messages: Array<{ role: string; content: string }>,
  sessionId?: string
) =>
  request<{
    content: string;
    model: string;
    runtime: string;
    session_id: string;
    sig_id: string | null;
    latency_ms: number;
  }>("POST", `/chat/${agentId}`, { messages, session_id: sessionId ?? null });

// Trust
export const getTrustProfile = (agentId: string) =>
  request<import("./types").TrustProfile>("GET", `/trust/profile/${agentId}`);
export const recalculateTrust = (agentId: string) =>
  request<import("./types").TrustProfile>("POST", `/trust/profile/${agentId}/recalculate`);
export const listSkillConnectors = (category?: string) => {
  const qs = category ? `?category=${category}` : "";
  return request<import("./types").SkillConnector[]>("GET", `/trust/skills/connectors${qs}`);
};
export const listAgentSkills = (agentId: string) =>
  request<import("./types").SkillBinding[]>("GET", `/trust/skills/${agentId}`);
