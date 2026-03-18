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
