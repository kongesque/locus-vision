Architecture Issues
1. State lives in the wrong place (High Priority)
The parent calls activityFeed?.addEvent() via bind:this — this tightly couples the parent to the child's API and prevents other components (e.g., a notification bell) from accessing event state.

Fix: Extract to a runes-based store with Svelte context:


// src/lib/stores/activity-feed.svelte.ts
export function createActivityFeedStore(eventTypeConfig: EventTypeConfig) {
  let events = $state<ActivityEvent[]>([]);
  let isPaused = $state(false);
  // ... all state + logic here
  
  return {
    get events() { return events; },
    get filteredEvents() { return filteredEvents; },
    addEvent,
    loadEvents,
    togglePause() { ... },
    clear() { ... },
  };
}
Then use setContext('activity-feed', store) in the page and getContext in the component. This is the recommended Svelte 5 pattern (SSR-safe, no globals).

2. No event batching — jank at high frequency (High Priority)
Every SSE message triggers a synchronous $state mutation at line 98: activityLogs = [newEvent, ...activityLogs].slice(0, 200) — copying up to 200 objects per event. Plus eventCounts = { ...eventCounts } at line 83 creates a new object every time.

Fix: Batch via microtask:


let pending: ActivityEvent[] = [];
let flushScheduled = false;

export function addEvent(message: string, type: EventType, zone?: string) {
  pending.push(createEvent(message, type, zone));
  if (!flushScheduled) {
    flushScheduled = true;
    queueMicrotask(() => {
      events = [...pending, ...events].slice(0, MAX_EVENTS);
      for (const ev of pending) {
        eventCounts[ev.type] = (eventCounts[ev.type] || 0) + 1;
      }
      eventCounts = eventCounts; // single reactivity trigger
      pending = [];
      flushScheduled = false;
    });
  }
}
Also replace crypto.randomUUID() with a simple counter (evt-${++nextId}) — these IDs are only used as {#each} keys.

SSE / Connection Issues
3. No reconnection gap handling (Medium Priority)
When the SSE connection drops and reconnects, events during the gap are lost. The backend already buffers recent events but the frontend doesn't request them on reconnect.

Fix: Add Last-Event-ID support. Backend sends id: field in SSE messages; on reconnection, the browser automatically sends Last-Event-ID and the backend replays missed events.

4. Tab backgrounding wastes resources (Medium Priority)
When the tab is hidden, Chrome throttles timers but SSE messages still queue up. The backend maintains a dead client queue (maxsize=100 at livestream.py:92).

Fix: Use the Page Visibility API:


document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    eventSource?.close();
  } else {
    reconnectSSE();
    fetchRecentEvents(); // backfill from ring buffer
  }
});
UX / Usability Issues
5. No event grouping — feed floods during busy periods (Medium Priority)
5 persons entering Zone A generates 5 rows. Monitoring tools (Datadog, Sentry) group similar events.

Fix: Sliding-window aggregation with a 3-second tumbling window:


function groupKey(type: string, zone?: string): string {
  const bucket = Math.floor(Date.now() / 3000);
  return `${type}:${zone ?? 'none'}:${bucket}`;
}
If the latest event in the list has a matching group key, increment its count and update lastSeen instead of adding a new row. Display as "Person entered Zone A (x5)". Never group critical events — they must always appear individually.

6. No audio/notification for critical alerts (Medium Priority)
If the operator is in another tab, critical alerts (wrong way, capacity warning) are invisible. This is a safety issue for a monitoring platform.

Fix — Tier 1 (audio, no permission needed):


let audioCtx: AudioContext | null = null;

function playAlertTone(freq = 880, duration = 0.15, repeat = 2) {
  if (!audioCtx) audioCtx = new AudioContext();
  for (let i = 0; i < repeat; i++) {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.connect(gain).connect(audioCtx.destination);
    osc.frequency.value = freq;
    gain.gain.value = 0.3;
    osc.start(audioCtx.currentTime + i * 0.2);
    osc.stop(audioCtx.currentTime + i * 0.2 + duration);
  }
}
Fix — Tier 2 (browser notifications when tab hidden):


if (document.hidden && Notification.permission === 'granted') {
  new Notification('LocusVision Alert', {
    body: message,
    tag: 'locus-alert', // deduplicates
    requireInteraction: true,
  });
}
Both should be opt-in via user settings.

7. No relative timestamps (Low Priority)
The feed shows 14:32:05 but monitoring UIs typically show "2s ago", "1m ago" for recent events. Use a derived value that updates on a 10-second interval rather than per-event.

Accessibility Issues
8. Missing ARIA semantics (Low Priority)
The feed <ul> at line 292 has no accessible role. Screen readers have no way to know this is a live event log.

Fixes:

Add role="log" and aria-label="Detection events" to the <ul>
Add a hidden <div aria-live="assertive" role="alert" class="sr-only"> that only announces critical events (never polite-announce the whole feed — screen readers would be overwhelmed at high frequency)
Add aria-pressed={activeEventFilter === key} to filter buttons
Wrap timestamps in <time datetime="..."> elements
What NOT to change
SSE is correct for this use case — unidirectional, auto-reconnects, HTTP/2 multiplexes. WebSocket would add complexity for no benefit.
No IndexedDB needed — the backend already persists events to DuckDB. Without the backend, the entire livestream is unavailable anyway.
Virtual scrolling is optional at 200 events — only add @tanstack/svelte-virtual if you raise the cap above 500.
Priority Summary
#	Change	Effort	Impact
1	Extract state to .svelte.ts store + context	Medium	Architectural foundation
2	Microtask batching for high-frequency events	Low	Prevents jank
3	Page Visibility API (pause SSE when hidden)	Low	Resource savings
4	Event grouping (3s window)	Medium	Major UX improvement
5	Audio alerts for critical events	Low	Safety improvement
6	Last-Event-ID for gapless reconnection	Medium	Backend + frontend change
7	ARIA role="log" + live region	Low	Accessibility
8	Browser notifications (tab hidden)	Low	Nice-to-have
Want me to implement any of these?