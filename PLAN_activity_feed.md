# Activity Feed — Industry Standard Implementation Plan

## Context

The activity feed component (`src/lib/components/livestream/activity-feed.svelte`) is well-built on the frontend. The core gap is that `StreamContext.recent_events` in `backend/services/livestream_manager.py` is an in-memory `deque(maxlen=200)` — events are lost when the backend process restarts. Everything else is secondary to fixing this.

---

## ✅ Priority 1 — Persist Livestream Events to SQLite (Backend Restart Survival)

**Problem:** `recent-events` endpoint reads from `ctx.recent_events` (memory deque). Backend restart = empty feed.

**Solution:** Add a `livestream_events` table to SQLite. On `StreamContext` startup, load the last N events for that camera. On every new event, write to DB. The memory deque stays as a fast read buffer — it's just populated from DB on init and kept in sync.

### 1a. Add `livestream_events` table — `backend/database.py`

Add to `executescript` in `init_db()`:

```sql
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
```

### 1b. Write events to SQLite — `backend/services/livestream_manager.py`

In `StreamContext._capture_loop`, where events are appended to `self.recent_events` (line ~290), also write to SQLite using a fire-and-forget async call or a small write queue to avoid blocking the capture thread.

Simplest approach — add a secondary thread buffer and flush to SQLite every 5s alongside the DuckDB flush in `_flush_duckdb()`:

```python
# In __init__
self.event_write_buffer = []  # pending SQLite writes

# In _capture_loop (alongside existing recent_events.append)
if ev.get("type") != "zone_update":
    self.recent_events.append(ev)
    self.event_write_buffer.append(ev)  # add this

# In _flush_duckdb() — add after existing flushes
self._flush_sqlite_events()

# New method
def _flush_sqlite_events(self):
    if not self.event_write_buffer:
        return
    import asyncio, aiosqlite
    from config import settings
    events = self.event_write_buffer[:]
    self.event_write_buffer.clear()
    # Run sync from the background thread
    import sqlite3
    try:
        conn = sqlite3.connect(settings.database_path)
        conn.executemany(
            "INSERT INTO livestream_events (camera_id, type, message, zone, timestamp) VALUES (?,?,?,?,?)",
            [(self.camera_id, e["type"], e["message"], e.get("zone"), e["timestamp"]) for e in events]
        )
        conn.commit()
        conn.close()
    except Exception as ex:
        print(f"[Livestream] SQLite event flush failed: {ex}")
```

> Use sync `sqlite3` (not aiosqlite) here because `_flush_duckdb` runs in the background capture thread, not an async context.

### 1c. Preload ring buffer on stream start — `backend/services/livestream_manager.py`

In `StreamContext.__init__` (or `start()`), query the last 200 events for this camera and populate `self.recent_events`:

```python
def _preload_recent_events(self):
    import sqlite3
    from config import settings
    try:
        conn = sqlite3.connect(settings.database_path)
        rows = conn.execute(
            "SELECT type, message, zone, timestamp FROM livestream_events "
            "WHERE camera_id = ? ORDER BY timestamp DESC LIMIT 200",
            (self.camera_id,)
        ).fetchall()
        conn.close()
        for row in reversed(rows):  # oldest first so deque order matches
            self.recent_events.append({
                "type": row[0], "message": row[1],
                "zone": row[2], "timestamp": row[3]
            })
    except Exception as ex:
        print(f"[Livestream] Event preload failed: {ex}")
```

Call `self._preload_recent_events()` at end of `StreamContext.__init__`.

### 1d. Retention cleanup — `backend/services/archiver.py`

Add to the existing archiver job (or run as a standalone periodic task):

```python
# Delete events older than 7 days
conn.execute(
    "DELETE FROM livestream_events WHERE timestamp < ?",
    (time.time() - 7 * 86400,)
)
```

---

## ✅ Priority 2 — Relative Timestamps with Full Timestamp on Hover (Frontend)

**Problem:** Feed shows `HH:MM:SS` only. Events from hours ago lose date context, and there's no quick way to see the full ISO timestamp.

**Solution:** Store the raw `timestamp` (Unix seconds) on each event. Display relative time ("2m ago", "1h ago") that auto-updates. Show full timestamp on hover as a `title` attribute.

### Changes — `src/lib/components/livestream/activity-feed.svelte`

**In `ActivityEvent` type**, add:
```ts
timestamp?: number  // Unix seconds
```

**In `addEvent()`**, store `Date.now() / 1000` as `timestamp`.

**In `loadEvents()`**, already receives `ev.timestamp` — pass it through to the mapped event.

**Add a reactive relative-time helper:**
```ts
function relativeTime(ts?: number): string {
    if (!ts) return ''
    const diff = Math.floor(Date.now() / 1000 - ts)
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
    return `${Math.floor(diff / 86400)}d ago`
}
```

**Update the timestamp display in the feed item:**
```svelte
<!-- replace: <span class="font-mono text-[10px] ...">{log.time}</span> -->
<span
    class="font-mono text-[10px] text-muted-foreground cursor-default"
    title={log.timestamp ? new Date(log.timestamp * 1000).toLocaleString() : log.time}
>
    {log.timestamp ? relativeTime(log.timestamp) : log.time}
</span>
```

**Add a `$effect` to refresh relative times every 30s:**
```ts
$effect(() => {
    const interval = setInterval(() => {
        activityLogs = [...activityLogs]  // trigger re-render
    }, 30_000)
    return () => clearInterval(interval)
})
```

---

## ✅ Priority 3 — Link to Full Event History (Frontend)

**Problem:** Feed is capped at 200 events with no escape hatch to the full searchable history.

**Solution:** Add a "View all events" footer link to the analytics/events page, filtered to this camera.

### Changes — `src/lib/components/livestream/activity-feed.svelte`

Add below the `</ul>` closing tag inside the feed content div:

```svelte
{#if activityLogs.length >= 200}
    <div class="border-t border-border/20 px-4 py-2.5 text-center">
        <a
            href="/analytics?camera={cameraId}"
            class="text-[11px] text-blue-400 hover:text-blue-300 transition-colors"
        >
            Showing 200 most recent · View full history →
        </a>
    </div>
{/if}
```

Pass `cameraId` as a new prop from the livestream page.

---

## Priority 4 — Export Button (Frontend, Low)

**Problem:** No way to export the current feed contents.

**Solution:** Add a download button to the feed toolbar that exports visible events as JSON or CSV.

### Changes — `src/lib/components/livestream/activity-feed.svelte`

Add export function:
```ts
function exportEvents() {
    const rows = filteredLogs.map(e =>
        `${e.time},${e.type},${JSON.stringify(e.message)},${e.zone ?? ''}`
    ).join('\n')
    const blob = new Blob([`time,type,message,zone\n${rows}`], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `events-${new Date().toISOString().slice(0,19)}.csv`
    a.click()
    URL.revokeObjectURL(url)
}
```

Add a download icon button to the toolbar alongside the existing pause/clear buttons.

---

## Priority 5 — Browser Notification for Critical Alerts (Frontend, Low)

**Problem:** `hasActiveAlert` only triggers a visual pulse. No notification if the tab is in the background.

**Solution:** Use the [Notification API](https://developer.mozilla.org/en-US/docs/Web/API/Notifications_API) for `severity === 'critical'` events.

### Changes — `src/lib/components/livestream/activity-feed.svelte`

In `addEvent()`, after the `hasActiveAlert = true` block:
```ts
if (severity === 'critical' && document.visibilityState === 'hidden') {
    if (Notification.permission === 'granted') {
        new Notification('LocusVision Alert', { body: message, icon: '/favicon.png' })
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission()
    }
}
```

Request permission once on component mount (only prompt if camera is connected):
```ts
$effect(() => {
    if (isConnected && Notification.permission === 'default') {
        Notification.requestPermission()
    }
})
```

---

## Implementation Order

| # | Task | Files | Effort |
|---|------|-------|--------|
| 1 | Add `livestream_events` table | `backend/database.py` | ~15 min |
| 2 | Write events to SQLite on flush | `backend/services/livestream_manager.py` | ~30 min |
| 3 | Preload ring buffer on stream start | `backend/services/livestream_manager.py` | ~20 min |
| 4 | Add retention cleanup | `backend/services/archiver.py` | ~10 min |
| 5 | Relative timestamps + hover tooltip | `src/lib/components/livestream/activity-feed.svelte` | ~20 min |
| 6 | "View full history" footer link | `src/lib/components/livestream/activity-feed.svelte` | ~10 min |
| 7 | Export button | `src/lib/components/livestream/activity-feed.svelte` | ~15 min |
| 8 | Browser notifications | `src/lib/components/livestream/activity-feed.svelte` | ~15 min |

Steps 1–4 are a single logical unit — do them together. Steps 5–8 are independent and can be done in any order.
