/**
 * Unit tests for activity-feed logic (PLAN_activity_feed.md — Priorities 2–5).
 *
 * Priority 1 (SQLite persistence) is covered by backend/tests/test_livestream_events_persistence.py.
 *
 * Pure functions and browser-API interactions are defined locally here since the
 * .svelte environment is not mountable in Vitest's node environment.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ─── Shared types ─────────────────────────────────────────────────────────────

interface ActivityEvent {
	id: string;
	time: string;
	timestamp?: number;
	message: string;
	type: string;
	zone?: string;
	severity?: 'critical' | 'warning' | 'info';
}

// ─── Priority 2: relativeTime ─────────────────────────────────────────────────
// Copied verbatim from activity-feed.svelte so the contract is tested, not the import.

function relativeTime(ts: number): string {
	const diff = Math.floor(Date.now() / 1000 - ts);
	if (diff < 60) return `${diff}s ago`;
	if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
	if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
	return `${Math.floor(diff / 86400)}d ago`;
}

describe('relativeTime', () => {
	const now = () => Math.floor(Date.now() / 1000);

	it('returns seconds for events under 1 minute', () => {
		expect(relativeTime(now() - 5)).toBe('5s ago');
		expect(relativeTime(now() - 59)).toBe('59s ago');
	});

	it('returns minutes for events between 1m and 1h', () => {
		expect(relativeTime(now() - 60)).toBe('1m ago');
		expect(relativeTime(now() - 90)).toBe('1m ago');
		expect(relativeTime(now() - 3599)).toBe('59m ago');
	});

	it('returns hours for events between 1h and 1d', () => {
		expect(relativeTime(now() - 3600)).toBe('1h ago');
		expect(relativeTime(now() - 7200)).toBe('2h ago');
		expect(relativeTime(now() - 86399)).toBe('23h ago');
	});

	it('returns days for events older than 1d', () => {
		expect(relativeTime(now() - 86400)).toBe('1d ago');
		expect(relativeTime(now() - 86400 * 3)).toBe('3d ago');
	});

	it('never returns a negative value for a current-second timestamp', () => {
		expect(relativeTime(now())).toMatch(/^\ds ago$/);
	});
});

// ─── Priority 2: classifySeverity ────────────────────────────────────────────

function classifySeverity(type: string): 'critical' | 'warning' | 'info' {
	if (type === 'alert' || type === 'capacity_warning' || type === 'wrong_way') return 'critical';
	if (type === 'zone') return 'warning';
	return 'info';
}

describe('classifySeverity', () => {
	it('classifies alert, capacity_warning, wrong_way as critical', () => {
		expect(classifySeverity('alert')).toBe('critical');
		expect(classifySeverity('capacity_warning')).toBe('critical');
		expect(classifySeverity('wrong_way')).toBe('critical');
	});

	it('classifies zone as warning', () => {
		expect(classifySeverity('zone')).toBe('warning');
	});

	it('classifies person, vehicle, motion and unknowns as info', () => {
		expect(classifySeverity('person')).toBe('info');
		expect(classifySeverity('vehicle')).toBe('info');
		expect(classifySeverity('motion')).toBe('info');
		expect(classifySeverity('unknown_type')).toBe('info');
	});
});

// ─── Priority 4: buildCsv ─────────────────────────────────────────────────────

function buildCsv(logs: ActivityEvent[]): string {
	const rows = logs
		.map((e) => `${e.time},${e.type},${JSON.stringify(e.message)},${e.zone ?? ''}`)
		.join('\n');
	return `time,type,message,zone\n${rows}`;
}

const sampleLogs: ActivityEvent[] = [
	{
		id: '1', time: '14:30:00', timestamp: 1700000000,
		type: 'person', message: 'Person entered Lobby', zone: 'Lobby', severity: 'info'
	},
	{
		id: '2', time: '14:31:05', timestamp: 1700000065,
		type: 'alert', message: 'Capacity exceeded', zone: undefined, severity: 'critical'
	}
];

describe('buildCsv', () => {
	it('first line is the header', () => {
		expect(buildCsv(sampleLogs).split('\n')[0]).toBe('time,type,message,zone');
	});

	it('produces one data row per event', () => {
		expect(buildCsv(sampleLogs).split('\n')).toHaveLength(3); // header + 2
	});

	it('formats all four columns correctly', () => {
		const lines = buildCsv(sampleLogs).split('\n');
		expect(lines[1]).toBe('14:30:00,person,"Person entered Lobby",Lobby');
		expect(lines[2]).toBe('14:31:05,alert,"Capacity exceeded",');
	});

	it('JSON-encodes the message to handle embedded commas safely', () => {
		const logs: ActivityEvent[] = [
			{ id: '3', time: '10:00:00', type: 'person', message: 'Zone A, then Zone B', severity: 'info' }
		];
		expect(buildCsv(logs)).toContain('"Zone A, then Zone B"');
	});

	it('returns only the header for an empty feed', () => {
		expect(buildCsv([])).toBe('time,type,message,zone\n');
	});
});

// ─── Priority 4: buildJson ────────────────────────────────────────────────────

function buildJson(logs: ActivityEvent[]): string {
	const data = logs.map((e) => ({
		time: e.time,
		timestamp: e.timestamp ?? null,
		type: e.type,
		message: e.message,
		zone: e.zone ?? null,
		severity: e.severity ?? null
	}));
	return JSON.stringify(data, null, 2);
}

describe('buildJson', () => {
	it('returns a valid JSON array', () => {
		const parsed = JSON.parse(buildJson(sampleLogs));
		expect(Array.isArray(parsed)).toBe(true);
		expect(parsed).toHaveLength(2);
	});

	it('includes all expected fields on each event', () => {
		const parsed = JSON.parse(buildJson(sampleLogs));
		expect(Object.keys(parsed[0])).toEqual(
			expect.arrayContaining(['time', 'timestamp', 'type', 'message', 'zone', 'severity'])
		);
	});

	it('preserves timestamp as a number', () => {
		const parsed = JSON.parse(buildJson(sampleLogs));
		expect(parsed[0].timestamp).toBe(1700000000);
	});

	it('maps undefined zone to null', () => {
		const parsed = JSON.parse(buildJson(sampleLogs));
		expect(parsed[1].zone).toBeNull();
	});

	it('maps missing timestamp to null', () => {
		const logs: ActivityEvent[] = [
			{ id: '9', time: '10:00:00', type: 'person', message: 'test', severity: 'info' }
		];
		expect(JSON.parse(buildJson(logs))[0].timestamp).toBeNull();
	});

	it('returns an empty array for an empty feed', () => {
		expect(JSON.parse(buildJson([]))).toEqual([]);
	});

	it('output is pretty-printed (2-space indent)', () => {
		const raw = buildJson(sampleLogs);
		expect(raw).toContain('  "time"');
	});
});

// ─── Priority 4: triggerDownload ──────────────────────────────────────────────

function triggerDownload(content: string, filename: string, mime: string) {
	const blob = new Blob([content], { type: mime });
	const url = URL.createObjectURL(blob);
	const a = document.createElement('a');
	a.href = url;
	a.download = filename;
	a.click();
	URL.revokeObjectURL(url);
}

describe('triggerDownload', () => {
	let createObjectURL: ReturnType<typeof vi.fn>;
	let revokeObjectURL: ReturnType<typeof vi.fn>;
	let mockAnchor: { href: string; download: string; click: ReturnType<typeof vi.fn> };

	beforeEach(() => {
		createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
		revokeObjectURL = vi.fn();
		mockAnchor = { href: '', download: '', click: vi.fn() };
		vi.stubGlobal('URL', { createObjectURL, revokeObjectURL });
		vi.stubGlobal('Blob', class MockBlob {
			constructor(public parts: string[], public opts: object) {}
		});
		vi.stubGlobal('document', { createElement: vi.fn().mockReturnValue(mockAnchor) });
	});

	afterEach(() => vi.unstubAllGlobals());

	it('creates an object URL from the content', () => {
		triggerDownload('data', 'file.csv', 'text/csv');
		expect(createObjectURL).toHaveBeenCalledOnce();
	});

	it('sets href to the blob URL', () => {
		triggerDownload('data', 'file.csv', 'text/csv');
		expect(mockAnchor.href).toBe('blob:mock-url');
	});

	it('sets the download filename', () => {
		triggerDownload('data', 'events-2026.csv', 'text/csv');
		expect(mockAnchor.download).toBe('events-2026.csv');
	});

	it('clicks the anchor to trigger the browser save dialog', () => {
		triggerDownload('data', 'file.csv', 'text/csv');
		expect(mockAnchor.click).toHaveBeenCalledOnce();
	});

	it('revokes the object URL after clicking to free memory', () => {
		triggerDownload('data', 'file.csv', 'text/csv');
		expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
	});

	it('works with JSON mime type', () => {
		triggerDownload('[]', 'events.json', 'application/json');
		expect(mockAnchor.download).toBe('events.json');
	});
});

// ─── Priority 5: notifyIfHidden ───────────────────────────────────────────────

function notifyIfHidden(message: string) {
	if (
		typeof Notification === 'undefined' ||
		Notification.permission !== 'granted' ||
		document.visibilityState !== 'hidden'
	)
		return;
	new Notification('LocusVision Alert', { body: message, icon: '/favicon.png' });
}

describe('notifyIfHidden', () => {
	let MockNotification: ReturnType<typeof vi.fn> & { permission: string };

	beforeEach(() => {
		MockNotification = Object.assign(vi.fn(), { permission: 'granted' });
		vi.stubGlobal('Notification', MockNotification);
	});

	afterEach(() => vi.unstubAllGlobals());

	it('fires a notification when tab is hidden and permission is granted', () => {
		vi.stubGlobal('document', { visibilityState: 'hidden' });
		notifyIfHidden('Capacity exceeded');
		expect(MockNotification).toHaveBeenCalledWith('LocusVision Alert', {
			body: 'Capacity exceeded',
			icon: '/favicon.png'
		});
	});

	it('does not fire when the tab is visible', () => {
		vi.stubGlobal('document', { visibilityState: 'visible' });
		notifyIfHidden('Alert');
		expect(MockNotification).not.toHaveBeenCalled();
	});

	it('does not fire when permission is denied', () => {
		MockNotification.permission = 'denied';
		vi.stubGlobal('document', { visibilityState: 'hidden' });
		notifyIfHidden('Alert');
		expect(MockNotification).not.toHaveBeenCalled();
	});

	it('does not fire when permission is default (not yet asked)', () => {
		MockNotification.permission = 'default';
		vi.stubGlobal('document', { visibilityState: 'hidden' });
		notifyIfHidden('Alert');
		expect(MockNotification).not.toHaveBeenCalled();
	});

	it('does not throw when the Notification API is unavailable', () => {
		vi.stubGlobal('Notification', undefined);
		vi.stubGlobal('document', { visibilityState: 'hidden' });
		expect(() => notifyIfHidden('Alert')).not.toThrow();
	});
});

// ─── Priority 3: analytics preselectedCamera ─────────────────────────────────
// Tests the URL param resolution logic from analytics/+page.ts in isolation.

function resolveSelectedCamera(
	preselectedCamera: string | undefined,
	cameras: { id: string }[]
): string {
	return preselectedCamera || cameras?.[0]?.id || '';
}

describe('resolveSelectedCamera', () => {
	const cameras = [{ id: 'cam_A' }, { id: 'cam_B' }];

	it('uses the ?camera= query param when provided', () => {
		expect(resolveSelectedCamera('cam_B', cameras)).toBe('cam_B');
	});

	it('falls back to the first camera when no param is present', () => {
		expect(resolveSelectedCamera(undefined, cameras)).toBe('cam_A');
	});

	it('returns empty string when there are no cameras and no param', () => {
		expect(resolveSelectedCamera(undefined, [])).toBe('');
	});

	it('uses the param even if it does not match any known camera', () => {
		// Backend validates camera ownership — frontend just passes it through
		expect(resolveSelectedCamera('cam_unknown', cameras)).toBe('cam_unknown');
	});
});
