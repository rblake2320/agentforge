export interface Agent {
  agent_id: string;
  owner_id: string;
  did_uri: string;
  display_name: string;
  agent_type: string;
  model_version: string;
  purpose: string;
  capabilities: string[];
  key_fingerprint: string;
  key_algorithm: string;
  is_active: boolean;
  is_public: boolean;
  preferred_runtime: string;
  created_at: string;
}

export interface AgentDetail extends Agent {
  did_document: Record<string, unknown>;
  verifiable_credential: Record<string, unknown>;
  behavioral_signature: Record<string, unknown>;
  routing_config: Record<string, unknown>;
}

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
}

// Wallet
export interface WalletKey {
  key_id: string;
  agent_id: string;
  key_version: number;
  created_at: string;
  revoked_at: string | null;
}

export interface Wallet {
  wallet_id: string;
  owner_id: string;
  created_at: string;
  keys: WalletKey[];
}

// Tamper
export interface TamperChain {
  signatures: Array<{
    sig_id: string;
    sequence_num: number;
    message_hash: string;
    created_at: string;
  }>;
  checkpoints: Array<{
    checkpoint_id: string;
    merkle_root: string;
    leaf_count: number;
    created_at: string;
  }>;
}

// Marketplace
export interface Listing {
  listing_id: string;
  agent_id: string;
  seller_id: string;
  title: string;
  description: string;
  price_cents: number;
  license_type: "perpetual" | "subscription" | "per_use";
  max_clones: number;
  total_sales: number;
  avg_rating: number | null;
  category: string;
  tags: string[];
  is_active: boolean;
  created_at: string;
}

export interface License {
  license_id: string;
  listing_id: string;
  buyer_id: string;
  clone_agent_id: string | null;
  license_key: string;
  status: "active" | "expired" | "revoked";
  starts_at: string;
  expires_at: string | null;
  usage_limit: number | null;
  usage_count: number;
  created_at: string;
}

export interface SellerRevenue {
  listings: number;
  total_licenses: number;
  active_licenses: number;
  total_gross_usd: number;
  total_net_usd: number;
}

// Portability
export interface Device {
  device_id: string;
  device_name: string;
  device_type: string;
  device_fingerprint: string;
  last_seen: string;
  created_at: string;
}

export interface MemoryEntry {
  memory_id: string;
  agent_id: string;
  layer: "hot" | "warm" | "cold";
  content_hash: string;
  summary: string;
  priority: number;
  created_at: string;
  accessed_at: string;
}

export interface SessionHandoff {
  handoff_id: string;
  agent_id: string;
  handoff_token: string;
  status: "pending" | "accepted" | "expired";
  expires_at: string;
  created_at: string;
}

// Trust
export interface TrustProfile {
  agent_id: string;
  overall_score: number;
  trust_level: "untrusted" | "provisional" | "trusted" | "verified" | "elite";
  technical_trust: number;
  reliability_trust: number;
  security_trust: number;
  tamper_violations: number;
  heartbeat_checks: number;
  uptime_pct: number;
  calculated_at: string;
}

export interface SkillConnector {
  connector_id: string;
  name: string;
  category: string;
  description: string;
  endpoint_url: string;
  auth_type: string;
  is_public: boolean;
  created_at: string;
}

export interface SkillBinding {
  binding_id: string;
  agent_id: string;
  connector_id: string;
  permissions: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}
