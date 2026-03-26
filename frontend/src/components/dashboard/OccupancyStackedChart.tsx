"use client";

import { useMemo } from "react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from "recharts";
import { DetectionEvent, Zone } from "@/utils/types";
import { CLASS_COLORS, DEFAULT_COLOR } from "@/utils/colors";

// Helper to get zone color from classIds
const getZoneColor = (zone: Zone) => CLASS_COLORS[zone.classIds[0]] || DEFAULT_COLOR;

interface OccupancyStackedChartProps {
    data: DetectionEvent[];
    zones: Zone[];
    duration?: number;
}

export default function OccupancyStackedChart({ data, zones, duration }: OccupancyStackedChartProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0 || !zones || zones.length === 0) return [];

        const maxTime = duration || Math.max(...data.map(d => d.time), 0);
        const bucketSize = Math.max(1, Math.floor(maxTime / 30)); // ~30 data points

        // Sort events by time
        const sortedData = [...data].sort((a, b) => a.time - b.time);

        // Track current occupancy per zone (using last known count)
        const currentCounts: Record<string, number> = {};
        zones.forEach(z => currentCounts[z.id] = 0);

        const timeline: Record<string, number | string>[] = [];
        let eventIdx = 0;

        const maxBucket = Math.ceil(maxTime / bucketSize);

        for (let i = 0; i <= maxBucket; i++) {
            const endTime = (i + 1) * bucketSize;

            // Update counts from events up to this time
            while (eventIdx < sortedData.length && sortedData[eventIdx].time < endTime) {
                const ev = sortedData[eventIdx];
                currentCounts[ev.zone_id] = ev.count;
                eventIdx++;
            }

            const bucket: Record<string, number | string> = {
                name: `${i * bucketSize}s`
            };

            // Copy current counts and calculate total
            let total = 0;
            zones.forEach(z => {
                bucket[z.id] = currentCounts[z.id];
                total += currentCounts[z.id];
            });
            bucket.total = total;

            timeline.push(bucket);
        }

        return timeline;
    }, [data, zones, duration]);

    if (!data || data.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No occupancy data available
            </div>
        );
    }

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                    data={chartData}
                    margin={{
                        top: 20,
                        right: 10,
                        left: -10,
                        bottom: 5,
                    }}
                >
                    <defs>
                        {zones.map((zone) => (
                            <linearGradient key={zone.id} id={`occupancy${zone.id}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={getZoneColor(zone)} stopOpacity={0.6} />
                                <stop offset="95%" stopColor={getZoneColor(zone)} stopOpacity={0.1} />
                            </linearGradient>
                        ))}
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" vertical={false} />
                    <XAxis
                        dataKey="name"
                        stroke="#666"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        tick={{ dy: 5 }}
                    />
                    <YAxis
                        stroke="#666"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        label={{ value: 'Count', angle: -90, position: 'insideLeft', fontSize: 10, fill: '#666' }}
                    />
                    <Legend
                        iconType="circle"
                        verticalAlign="top"
                        align="right"
                        wrapperStyle={{ fontSize: '10px', paddingBottom: '8px', top: 0, right: 0 }}
                    />
                    {zones.map((zone) => (
                        <Area
                            key={zone.id}
                            type="monotone"
                            dataKey={zone.id}
                            stroke={getZoneColor(zone)}
                            strokeWidth={1.5}
                            fillOpacity={1}
                            fill={`url(#occupancy${zone.id})`}
                            name={zone.label}
                            stackId="1"
                            isAnimationActive={false}
                        />
                    ))}
                    <Tooltip
                        contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px', fontSize: '12px' }}
                        itemStyle={{ color: '#fff' }}
                        labelStyle={{ color: '#999', marginBottom: '4px' }}
                        allowEscapeViewBox={{ x: false, y: true }}
                        wrapperStyle={{ zIndex: 100 }}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}
