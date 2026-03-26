"use client";

import { useMemo } from "react";
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend
} from "recharts";
import { DetectionEvent, Zone } from "@/utils/types";

interface PeakTimeChartProps {
    data: DetectionEvent[];
    zones: Zone[];
    duration?: number;
}

export default function PeakTimeChart({ data, zones, duration }: PeakTimeChartProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Aggregate by time buckets (e.g. 10% of duration or fixed intervals)
        const maxTime = duration || Math.max(...data.map(d => d.time), 0);
        // Ensure at least 10 buckets, max 20, or 1 bucket per seond if short
        const bucketSize = Math.max(1, Math.ceil(maxTime / 20));
        const maxBucket = Math.ceil(maxTime / bucketSize);

        const timeline: Record<string, number | string>[] = [];

        for (let i = 0; i <= maxBucket; i++) {
            const timePoint = i * bucketSize;
            const bucket: Record<string, number | string> = { name: `${timePoint}s` };
            zones.forEach(z => bucket[z.id] = 0);
            timeline.push(bucket);
        }

        // Fill buckets with Max count seen in that interval
        data.forEach(event => {
            const bucketIndex = Math.floor(event.time / bucketSize);
            if (bucketIndex >= 0 && bucketIndex < timeline.length) {
                const zoneId = event.zone_id;
                // If the event count is higher than what we have recorded for this bucket, update it
                if (event.count > (timeline[bucketIndex][zoneId] as number)) {
                    timeline[bucketIndex][zoneId] = event.count;
                }
            }
        });

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
        <div className="h-full w-full overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart
                    data={chartData}
                    margin={{
                        top: 5,
                        right: 0,
                        left: 0,
                        bottom: 5,
                    }}
                >
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
                    <Tooltip
                        contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px', fontSize: '12px' }}
                        itemStyle={{ color: '#fff' }}
                        labelStyle={{ color: '#999', marginBottom: '4px' }}
                    />
                    <Legend
                        iconType="circle"
                        verticalAlign="top"
                        align="right"
                        wrapperStyle={{ fontSize: '10px', paddingBottom: '10px', top: 0, right: 0 }}
                    />
                    {zones.map((zone) => (
                        <Line
                            key={zone.id}
                            type="monotone"
                            dataKey={zone.id}
                            stroke={`rgb(${zone.color?.join(",")})`}
                            strokeWidth={2}
                            dot={false}
                            activeDot={{ r: 4 }}
                            name={zone.label}
                            isAnimationActive={false}
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
