"use client";

import { useMemo } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    Tooltip,
    ResponsiveContainer,
    Cell
} from "recharts";
import { DwellEvent, Zone } from "@/utils/types";
import { ANALYTICS_COLORS } from "@/utils/colors";

interface DwellDistributionChartProps {
    data: DwellEvent[];
    zones: Zone[];
}

// Define dwell time buckets using unified colors
const DWELL_BUCKETS = [
    { label: "0-5s", min: 0, max: 5, color: ANALYTICS_COLORS.dwellBuckets[0] },
    { label: "5-15s", min: 5, max: 15, color: ANALYTICS_COLORS.dwellBuckets[1] },
    { label: "15-30s", min: 15, max: 30, color: ANALYTICS_COLORS.dwellBuckets[2] },
    { label: "30-60s", min: 30, max: 60, color: ANALYTICS_COLORS.dwellBuckets[3] },
    { label: "60s+", min: 60, max: Infinity, color: ANALYTICS_COLORS.dwellBuckets[4] },
];

interface ZoneChartData {
    zone: Zone;
    buckets: { label: string; count: number; color: string }[];
}

export default function DwellDistributionChart({ data, zones }: DwellDistributionChartProps) {
    const zoneCharts = useMemo(() => {
        if (!data || data.length === 0 || !zones || zones.length === 0) {
            return [];
        }

        // Build chart data per zone
        const charts: ZoneChartData[] = zones.map(zone => {
            const zoneDwells = data.filter(d => d.zone_id === zone.id);

            const buckets = DWELL_BUCKETS.map(bucket => {
                const count = zoneDwells.filter(
                    d => d.duration >= bucket.min && d.duration < bucket.max
                ).length;
                return { label: bucket.label, count, color: bucket.color };
            });

            return { zone, buckets };
        });

        return charts;
    }, [data, zones]);

    if (!data || data.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No dwell data available
            </div>
        );
    }

    return (
        <div className="h-full w-full grid gap-2" style={{ gridTemplateColumns: `repeat(${Math.min(zones.length, 2)}, 1fr)` }}>
            {zoneCharts.map(({ zone, buckets }) => (
                <div key={zone.id} className="flex flex-col min-h-0">
                    {/* Zone Label */}
                    <div className="flex items-center gap-1.5 mb-1">
                        <div
                            className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ backgroundColor: `rgb(${zone.color.join(",")})` }}
                        />
                        <span className="text-[10px] text-secondary-text truncate">{zone.label}</span>
                    </div>
                    {/* Mini Bar Chart */}
                    <div className="flex-1 min-h-0">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart
                                data={buckets}
                                margin={{ top: 0, right: 0, left: -20, bottom: 0 }}
                            >
                                <XAxis
                                    dataKey="label"
                                    stroke="#666"
                                    fontSize={8}
                                    tickLine={false}
                                    axisLine={false}
                                    interval={0}
                                />
                                <YAxis
                                    stroke="#666"
                                    fontSize={8}
                                    tickLine={false}
                                    axisLine={false}
                                    width={20}
                                />
                                <Tooltip
                                    cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                                    contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '6px', fontSize: '10px' }}
                                    itemStyle={{ color: '#fff' }}
                                    formatter={((value: number | undefined) => [`${value ?? 0}`, 'Count']) as never}
                                />
                                <Bar dataKey="count" radius={[2, 2, 0, 0]} isAnimationActive={false}>
                                    {buckets.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} />
                                    ))}
                                </Bar>
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            ))}
        </div>
    );
}
