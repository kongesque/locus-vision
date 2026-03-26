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

interface ActivityTimelineProps {
    data: DetectionEvent[];
    zones: Zone[];
    duration?: number; // Total video duration in seconds
}

export default function ActivityTimeline({ data, zones, duration }: ActivityTimelineProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Aggregate data by second (or larger bucket if long video)
        // For now, let's assume we want second-by-second granularity

        // Find max time to set domain
        const maxTime = duration || Math.max(...data.map(d => d.time), 0);

        // Initialize time buckets
        const timeMap = new Map<number, Record<string, number>>();

        // Pre-fill with 0s for all seconds (optional, but good for smooth chart)
        for (let t = 0; t <= Math.ceil(maxTime); t++) {
            const emptyEntry: Record<string, number> = { time: t };
            zones.forEach(z => {
                emptyEntry[z.id] = 0;
            });
            timeMap.set(t, emptyEntry);
        }

        // Fill with actual data
        // Note: detectionData usually contains "events". If it's sparse, we might need to fill gaps.
        // Assuming detectionData is a stream of events where count changed.

        // Actually, looking at the backend code:
        // detection_events.append(...) happens in the loop.
        // It logs a snapshot when IN/OUT happens or when an object is counted.
        // This might be sparse. To make an Area chart, we might need to hold the "state" (current count).

        // Let's create a stateful timeline.
        const timeline: Record<string, number | string>[] = [];
        const currentCounts: Record<string, number> = {};
        zones.forEach(z => currentCounts[z.id] = 0);

        // Sort events by time
        const sortedData = [...data].sort((a, b) => a.time - b.time);

        let eventIdx = 0;

        // If we have dwelling data, "count" in event might be total cumulative or current?
        // Backend: "count": len(crossed_objects_per_zone[zone_id]) -> This is CUMULATIVE unique count for polygon.
        // For line: "count": lc['in'] + lc['out'] -> CUMULATIVE total crossings.

        // Wait, the user likely wants "Current Activity" (how many people are there NOW) or "Rate of Entry"?
        // "Object counting and observation dashboard" usually implies "Traffic over time".
        // If we just plot cumulative, it will always go up. That's fine if that's what we want.
        // specific request: "Activity Timeline". 
        // Let's plot "Activity" as events per time bucket (e.g. per 5 seconds) to show density of events.

        const bucketSize = 5; // seconds
        const maxBucket = Math.ceil(maxTime / bucketSize);

        for (let i = 0; i <= maxBucket; i++) {
            const startTime = i * bucketSize;
            const endTime = (i + 1) * bucketSize;

            const bucket: Record<string, number | string> = { name: `${startTime}s` };

            zones.forEach(z => bucket[z.id] = 0);

            // Count events in this bucket
            while (eventIdx < sortedData.length && sortedData[eventIdx].time < endTime) {
                const ev = sortedData[eventIdx];
                if (typeof bucket[ev.zone_id] === 'number') {
                    (bucket[ev.zone_id] as number)++;
                }
                eventIdx++;
            }

            timeline.push(bucket);
        }

        return timeline;
    }, [data, zones, duration]);

    if (!data || data.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No activity data available
            </div>
        );
    }

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart
                    data={chartData}
                    margin={{
                        top: 5,
                        right: 10,
                        left: 0,
                        bottom: 5,
                    }}
                >
                    <defs>
                        {zones.map((zone) => (
                            <linearGradient key={zone.id} id={`color${zone.id}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={getZoneColor(zone)} stopOpacity={0.4} />
                                <stop offset="95%" stopColor={getZoneColor(zone)} stopOpacity={0} />
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
                        mirror={true}
                    />
                    <Legend
                        iconType="circle"
                        verticalAlign="top"
                        align="right"
                        wrapperStyle={{ fontSize: '10px', paddingBottom: '10px', top: 0, right: 0 }}
                        formatter={(value) => <span style={{ marginRight: '10px' }}>{value}</span>}
                    />
                    {zones.map((zone) => (
                        <Area
                            key={zone.id}
                            type="monotone"
                            dataKey={zone.id}
                            stroke={getZoneColor(zone)}
                            strokeWidth={2}
                            fillOpacity={1}
                            fill={`url(#color${zone.id})`}
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
