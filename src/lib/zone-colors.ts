export const ZONE_COLOR_PALETTE = [
	'#fbbd05',
	'#3b82f6',
	'#10b981',
	'#ef4444',
	'#a855f7',
	'#ec4899',
	'#06b6d4',
	'#f97316'
];

export function pickZoneColor(usedColors: string[]): string {
	for (const c of ZONE_COLOR_PALETTE) {
		if (!usedColors.includes(c)) return c;
	}
	return ZONE_COLOR_PALETTE[usedColors.length % ZONE_COLOR_PALETTE.length];
}

export function hexToRgba(hex: string, alpha: number): string {
	const h = hex.replace('#', '');
	if (h.length !== 6) return `rgba(251, 189, 5, ${alpha})`;
	const r = parseInt(h.substring(0, 2), 16);
	const g = parseInt(h.substring(2, 4), 16);
	const b = parseInt(h.substring(4, 6), 16);
	return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
