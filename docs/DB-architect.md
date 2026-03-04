# LocusVision Database Architecture

LocusVision employs a **Dual-Database Architecture** to handle two fundamentally different types of workloads: 
1. Low-volume, transactional application state (Users, Settings, Cameras).
2. High-volume, time-series analytical data (Object trajectories, Zone events, Line crossings).

By separating these concerns, the system maintains high responsiveness for the web UI while efficiently ingesting and querying massive amounts of AI-generated spatial telemetry.

---

## 1. Application State Database (SQLite)

**Technology**: Asynchronous SQLite (`aiosqlite`)
**Location**: `backend/data/locusvision.db` (Configurable via Environment Variables)
**Role**: Manages the core transactional application state, user accounts, and system configuration.

### Configuration & Optimization
- **WAL Mode** (`PRAGMA journal_mode=WAL`): Enabled to allow concurrent reads and writes, preventing database locking and ensuring high concurrency.
- **Foreign Keys** (`PRAGMA foreign_keys=ON`): Enforced for data integrity (e.g., cascading deletes for sessions when a user is removed).

### Core Schema

#### `users`
Stores user accounts and authentication data.
- `id` (INTEGER, PK): Unique identifier.
- `email` (TEXT, UNIQUE): User's email address.
- `name` (TEXT): Display name.
- `password_hash` (TEXT): Argon2 hashed password.
- `role` (TEXT): `admin` or `viewer` (default).
- `is_active` (INTEGER): For disabling accounts (default `1`).
- `created_at` / `updated_at`: Timestamps.

#### `sessions`
Manages user authentication sessions and refresh tokens.
- `id` (INTEGER, PK)
- `user_id` (INTEGER, FK): References `users(id)` with `ON DELETE CASCADE`.
- `refresh_token_hash` (TEXT): Hashed refresh token to verify ongoing sessions.
- `expires_at` (TEXT): Expiration timestamp.
- `created_at` (TEXT): Timestamp.

#### `app_settings`
Key-value store for global application configurations.
- `key` (TEXT, PK): Setting identifier (e.g., `allow_signup`).
- `value` (TEXT): Setting value.

#### `cameras`
Stores configuration and metadata for active video sources.
- `id` (TEXT, PK): Unique camera identifier.
- `name` (TEXT): Display name.
- `type` (TEXT): Type of source (`rtsp` by default, but extensible).
- `url` (TEXT): The stream/video URL.
- `device_id` (TEXT): Hardware identifier (if applicable).
- `model_name` (TEXT): AI model to use (default: `yolo11n`).
- `status` (TEXT): Camera state (`active`, etc.).
- `zones` (TEXT): JSON representation of polygon zones.
- `classes` (TEXT): JSON list of classes to detect (e.g., `["person", "car"]`).
- `created_at` / `updated_at`: Timestamps.

#### `video_tasks`
Tracks offline/VOD video processing jobs and their results.
- `id` (TEXT, PK): Unique task ID.
- `filename` (TEXT): Original video filename.
- `status` (TEXT): Job state (`pending`, `processing`, `completed`, `failed`).
- `progress` (INTEGER): Processing percentage (0-100).
- `created_at` / `completed_at`: Timestamps.
- `duration` / `format`: Media metadata.
- `model_name` (TEXT): Model used for the task.
- `total_count` (INTEGER): Overall number of detections.
- `zone_counts` / `zones` / `classes`: JSON data containing detection summaries.
- `error_message` (TEXT): Reason for failure, if applicable.

---

## 2. Spatial Analytics & Telemetry Database (DuckDB)

**Technology**: DuckDB (Embedded OLAP Columnar Database)
**Location**: `backend/data/locus_active.duckdb`
**Role**: A highly specialized time-series and analytics database optimized for high-throughput insertion and rapid aggregation queries over millions of tracking events.

*(Note: DuckDB replaced previous iterations using TimescaleDB/InfluxDB to drastically simplify deployment while maintaining elite analytical query performance).*

### Core Schema

#### `zone_events`
Records when an object enters, dwells in, or exits a defined spatial zone.
- `timestamp` (TIMESTAMP): Event time.
- `camera_id` (VARCHAR): Source identifier.
- `zone_id` (VARCHAR): The configured zone boundary.
- `event_type` (VARCHAR): Typically `enter`, `exit`, etc.
- `track_id` (INTEGER): Unique tracking ID for the object.
- `dwell_time` (FLOAT): How long the object remained in the zone.

#### `line_events`
Records instances where an object crosses a defined virtual tripwire/line.
- `timestamp` (TIMESTAMP): Event time.
- `camera_id` (VARCHAR): Source identifier.
- `line_id` (VARCHAR): The configured line boundary.
- `direction` (VARCHAR): Direction of crossing (e.g., `in`, `out`).
- `track_id` (INTEGER): Unique tracking ID.

#### `object_tracks`
Raw, granular trajectory data recording the movement of objects frame by frame.
- `timestamp` (TIMESTAMP): Time of detection.
- `camera_id` (VARCHAR): Source identifier.
- `track_id` (INTEGER): Persistent identifier from tracking algorithms (e.g., ByteTrack).
- `class_id` (INTEGER): The type of object (from model labels).
- `x` / `y` (FLOAT): Center coordinates of the object.

#### `hourly_zone_stats` (Materialized/Aggregated)
Aggregates `zone_events` to optimize long-term reporting. Maintained by the `Downsampler` background service.
- `hour` (TIMESTAMP): Truncated to the hour.
- `camera_id` / `zone_id`: Spatial identifiers.
- `unique_visitors` (INTEGER): `COUNT(DISTINCT track_id)`.
- `avg_dwell_time` (FLOAT): Average time spent in zone for that hour.

---

## 3. Data Lifecycle & Maintenance Services

LocusVision implements background services to manage the immense volume of telemetry data without degrading system performance or exhausting disk space.

### The Downsampler (`services/downsampler.py`)
- **Purpose**: Aggregates raw, granular tracking stats (`object_tracks`, `zone_events`) into high-level summaries (such as `hourly_zone_stats`).
- **Interval**: Runs periodically (e.g., hourly).
- **Benefit**: Ensures that querying data from 3 months ago takes milliseconds, as the UI queries the pre-aggregated summary instead of millions of distinct trajectories.

### The Archiver (`services/archiver.py`)
- **Purpose**: Enforces data retention policies and exports old data for cold storage.
- **Interval**: Checks daily by default.
- **Action**:
  1. Identifies telemetry data (zone events, line events, object tracks) older than the configured retention period (default 30 days).
  2. Exports these older records into partitioned `.parquet` files stored in `data/archives/` (e.g., `zone_events_2024_01.parquet`).
  3. Deletes the old records from the active `locus_active.duckdb` database.
- **Benefit**: Keeps the active DuckDB instance small and incredibly fast, while ensuring compliance and enabling historical data recovery via Parquet files.
