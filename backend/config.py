"""Application configuration using pydantic-settings."""

from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    # ── JWT ──────────────────────────────────────────────
    jwt_secret: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # ── Argon2id (OWASP 2025 minimum for constrained devices) ──
    argon2_time_cost: int = 2
    argon2_memory_cost: int = 19_456  # 19 MiB
    argon2_parallelism: int = 1

    # ── Database ─────────────────────────────────────────
    database_path: str = str(BASE_DIR / "data" / "locusvision.db")

    # ── App ──────────────────────────────────────────────
    app_name: str = "LocusVision"
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:4173",
        "http://localhost:3000",
    ]

    # ── Rate Limiting ────────────────────────────────────
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300  # 5 minutes

    model_config = {"env_prefix": "LOCUS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
