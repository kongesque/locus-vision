// Generate color using Golden Angle Approximation (matches backend detector.py)
function getColorFromClassId(classId: number): string {
    const hue = ((classId * 137.508) % 360) / 360.0;
    const saturation = 0.85;
    const lightness = 0.55;

    // Convert HLS to RGB (note: CSS hsl uses different format)
    // We need to match Python's colorsys.hls_to_rgb behavior
    const h = hue;
    const l = lightness;
    const s = saturation;

    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs((h * 6) % 2 - 1));
    const m = l - c / 2;

    let r = 0, g = 0, b = 0;
    const h6 = h * 6;

    if (h6 < 1) { r = c; g = x; b = 0; }
    else if (h6 < 2) { r = x; g = c; b = 0; }
    else if (h6 < 3) { r = 0; g = c; b = x; }
    else if (h6 < 4) { r = 0; g = x; b = c; }
    else if (h6 < 5) { r = x; g = 0; b = c; }
    else { r = c; g = 0; b = x; }

    const R = Math.round((r + m) * 255);
    const G = Math.round((g + m) * 255);
    const B = Math.round((b + m) * 255);

    return `rgb(${R}, ${G}, ${B})`;
}

// Pre-computed CLASS_COLORS using Golden Angle algorithm (matches backend bounding boxes)
export const CLASS_COLORS: Record<number, string> = {};

// Generate colors for common COCO classes (0-79)
for (let i = 0; i <= 79; i++) {
    CLASS_COLORS[i] = getColorFromClassId(i);
}

export const DEFAULT_COLOR = "#6b7280";

export const getZoneColor = (classId: number): string => {
    return CLASS_COLORS[classId] || DEFAULT_COLOR;
};

// Unified Analytics Color Palette
export const ANALYTICS_COLORS = {
    // Primary semantic colors
    positive: "#22c55e",   // Green - entries, gains, success
    negative: "#ef4444",   // Red - exits, losses, warnings
    primary: "#3b82f6",    // Blue - primary metric, neutral
    secondary: "#8b5cf6",  // Purple - secondary metric

    // Chart UI colors
    grid: "#333333",
    axis: "#666666",

    // Metric-specific colors (for Zone Comparison)
    visitors: "#3b82f6",   // Blue - total visitors
    peak: "#f97316",       // Orange - peak values
    dwell: "#a855f7",      // Purple - dwell time

    // Dwell time buckets (gradient from quick to long)
    dwellBuckets: [
        "#22c55e",  // 0-5s - Quick pass (green)
        "#84cc16",  // 5-15s - Brief stop (lime)
        "#eab308",  // 15-30s - Moderate (yellow)
        "#f97316",  // 30-60s - High interest (orange)
        "#ef4444",  // 60s+ - Extended (red)
    ]
};

// Shared chart tooltip styles
export const CHART_STYLES = {
    tooltip: {
        backgroundColor: '#111',
        borderColor: '#333',
        borderRadius: '8px',
        fontSize: '12px'
    },
    tooltipItem: {
        color: '#fff'
    },
    tooltipLabel: {
        color: '#999',
        marginBottom: '4px'
    }
};
