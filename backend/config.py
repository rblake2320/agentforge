from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "AgentForge"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:%3FBooker78%21@localhost:5432/agentvault"

    # JWT (EdDSA — asymmetric)
    jwt_private_key_pem: str = ""   # Ed25519 private key PEM, set in .env
    jwt_public_key_pem: str = ""    # Ed25519 public key PEM, set in .env
    jwt_algorithm: str = "EdDSA"

    @property
    def jwt_private_key(self) -> str:
        """Return private key PEM with real newlines (handles escaped \\n from .env)."""
        return self.jwt_private_key_pem.replace("\\n", "\n")

    @property
    def jwt_public_key(self) -> str:
        """Return public key PEM with real newlines."""
        return self.jwt_public_key_pem.replace("\\n", "\n")
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # Auth
    max_login_attempts: int = 5
    login_lockout_minutes: int = 60

    # Argon2id params (OWASP 2024 minimum)
    argon2_memory_cost: int = 131072   # 128 MiB
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4
    argon2_hash_len: int = 32

    # NIM runtime
    nim_base_url: str = "http://localhost:8000"
    nim_model_name: str = "qwen2.5-32b"
    ngc_api_key: str = ""

    # Domain (for DID generation)
    agentforge_domain: str = "agentforge.dev"

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
