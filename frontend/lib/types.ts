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
