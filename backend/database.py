"""Async SQLite database setup and table creation."""

import aiosqlite
from pathlib import Path
from config import settings


async def get_db() -> aiosqlite.Connection:
    """Get an async database connection."""
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = await aiosqlite.connect(str(db_path))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Create tables if they don't exist."""
    db = await get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                name        TEXT    NOT NULL,
                password_hash TEXT  NOT NULL,
                role        TEXT    NOT NULL DEFAULT 'viewer',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                refresh_token_hash  TEXT    NOT NULL,
                expires_at          TEXT    NOT NULL,
                created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);

            -- Default app settings
            INSERT OR IGNORE INTO app_settings (key, value) VALUES ('allow_signup', 'false');
            INSERT OR IGNORE INTO app_settings (key, value) VALUES ('default_model', 'yolo11n');

            CREATE TABLE IF NOT EXISTS video_tasks (
                id            TEXT    PRIMARY KEY,
                filename      TEXT    NOT NULL,
                name          TEXT    NULL,
                status        TEXT    NOT NULL DEFAULT 'pending',
                progress      INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
                completed_at  TEXT    NULL,
                duration      TEXT    NULL,
                format        TEXT    NULL,
                model_name    TEXT    NULL,
                fps           INTEGER NULL DEFAULT 12,
                confidence_threshold REAL NULL DEFAULT 0.25,
                total_count   INTEGER NULL,
                zone_counts   TEXT    NULL,
                zones         TEXT    NULL,
                classes       TEXT    NULL,
                error_message TEXT    NULL
            );

            CREATE TABLE IF NOT EXISTS cameras (
                id          TEXT    PRIMARY KEY,
                name        TEXT    NOT NULL,
                type        TEXT    NOT NULL DEFAULT 'rtsp',
                url         TEXT    NULL,
                device_id   TEXT    NULL,
                model_name  TEXT    NOT NULL DEFAULT 'yolo11n',
                fps         INTEGER NOT NULL DEFAULT 24,
                confidence_threshold REAL NOT NULL DEFAULT 0.25,
                status      TEXT    NOT NULL DEFAULT 'active',
                zones       TEXT    NULL,
                classes     TEXT    NULL,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS livestream_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                camera_id  TEXT    NOT NULL,
                type       TEXT    NOT NULL,
                message    TEXT    NOT NULL,
                zone       TEXT    NULL,
                timestamp  REAL    NOT NULL,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_livestream_events_camera
                ON livestream_events(camera_id, timestamp DESC);

        """)
        await db.commit()

        # Migrate existing databases: add new columns if they don't exist
        try:
            cursor = await db.execute("PRAGMA table_info(video_tasks)")
            columns = [row[1] for row in await cursor.fetchall()]
            migrations = {
                "progress": "ALTER TABLE video_tasks ADD COLUMN progress INTEGER NOT NULL DEFAULT 0",
                "zones": "ALTER TABLE video_tasks ADD COLUMN zones TEXT NULL",
                "classes": "ALTER TABLE video_tasks ADD COLUMN classes TEXT NULL",
                "error_message": "ALTER TABLE video_tasks ADD COLUMN error_message TEXT NULL",
                "name": "ALTER TABLE video_tasks ADD COLUMN name TEXT NULL",
                "fps": "ALTER TABLE video_tasks ADD COLUMN fps INTEGER NULL DEFAULT 12",
                "confidence_threshold": "ALTER TABLE video_tasks ADD COLUMN confidence_threshold REAL NULL DEFAULT 0.25",
            }
            for col_name, sql in migrations.items():
                if col_name not in columns:
                    await db.execute(sql)
            await db.commit()
        except Exception as e:
            print(f"Migration warning (video_tasks): {e}")

        # Migrate cameras table
        try:
            cursor = await db.execute("PRAGMA table_info(cameras)")
            columns = [row[1] for row in await cursor.fetchall()]
            camera_migrations = {
                "updated_at": "ALTER TABLE cameras ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'))",
                "fps": "ALTER TABLE cameras ADD COLUMN fps INTEGER NOT NULL DEFAULT 24",
                "confidence_threshold": "ALTER TABLE cameras ADD COLUMN confidence_threshold REAL NOT NULL DEFAULT 0.25",
            }
            for col_name, sql in camera_migrations.items():
                if col_name not in columns:
                    await db.execute(sql)
            await db.commit()
        except Exception as e:
            print(f"Migration warning (cameras): {e}")

    finally:
        await db.close()


async def has_users() -> bool:
    """Check if any users exist (for initial setup flow)."""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) as count FROM users")
        row = await cursor.fetchone()
        return row[0] > 0  # type: ignore
    finally:
        await db.close()


async def get_app_setting(key: str, default: str = "") -> str:
    """Get an app setting by key."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row[0] if row else default  # type: ignore
    finally:
        await db.close()


async def set_app_setting(key: str, value: str):
    """Set an app setting (upsert)."""
    db = await get_db()
    try:
        await db.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        await db.commit()
    finally:
        await db.close()

