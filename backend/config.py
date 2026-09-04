"""Application configuration using pydantic-settings."""

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_JWT_SECRET = "change-me-in-production-use-openssl-rand-hex-32"


class Settings(BaseSettings):
    # ── JWT ──────────────────────────────────────────────
    jwt_secret: str = DEFAULT_JWT_SECRET
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
    cors_origin_regex: str = (
        r"^https?://(?:localhost|127\.0\.0\.1|\[::1\]|"
        r"10(?:\.\d{1,3}){3}|192\.168(?:\.\d{1,3}){2}|"
        r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2}|"
        r"[a-zA-Z0-9-]+\.local)(?::\d+)?$"
    )

    # ── Rate Limiting ────────────────────────────────────
    login_max_attempts: int = 5
    login_lockout_seconds: int = 300  # 5 minutes

    model_config = {"env_prefix": "LOCUS_", "env_file": ".env", "extra": "ignore"}


settings = Settings()


def _load_or_create_jwt_secret() -> None:
    """Persist a unique signing key beside the database when none is configured."""
    if settings.jwt_secret != DEFAULT_JWT_SECRET:
        return

    secret_path = Path(settings.database_path).expanduser().parent / ".jwt-secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        secret = secret_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        secret = secrets.token_urlsafe(48)
        try:
            fd = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            secret = secret_path.read_text(encoding="utf-8").strip()
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as secret_file:
                secret_file.write(f"{secret}\n")

    if len(secret) < 32:
        raise RuntimeError(f"JWT secret in {secret_path} must contain at least 32 characters")

    settings.jwt_secret = secret


_load_or_create_jwt_secret()
