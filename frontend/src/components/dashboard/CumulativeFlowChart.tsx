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
    Legend,
    ReferenceLine
} from "recharts";
import { Zone, LineCrossing, DetectionEvent } from "@/utils/types";
import { ANALYTICS_COLORS, CHART_STYLES } from "@/utils/colors";

interface CumulativeFlowChartProps {
    detectionData: DetectionEvent[];
    lineCrossingData: Record<string, LineCrossing>;
    zones: Zone[];
    duration?: number;
}

export default function CumulativeFlowChart({ detectionData, lineCrossingData, zones, duration }: CumulativeFlowChartProps) {
    const chartData = useMemo(() => {
        if (!detectionData || detectionData.length === 0) return [];

        // Get zones that have line crossing data
        const lineZones = zones.filter(z => lineCrossingData?.[z.id]);
        if (lineZones.length === 0) return [];

        const maxTime = duration || Math.max(...detectionData.map(d => d.time), 0);
        const bucketSize = Math.max(1, Math.floor(maxTime / 25)); // ~25 data points

        // Track cumulative counts
        const cumulativeCounts: Record<string, { in: number; out: number; net: number }> = {};
        lineZones.forEach(z => cumulativeCounts[z.id] = { in: 0, out: 0, net: 0 });

        // Sort events by time
        const sortedData = [...detectionData].sort((a, b) => a.time - b.time);

        const timeline: Record<string, number | string>[] = [];
        let eventIdx = 0;

        const maxBucket = Math.ceil(maxTime / bucketSize);

        for (let i = 0; i <= maxBucket; i++) {
            const endTime = (i + 1) * bucketSize;

            // Update cumulative counts from events
            while (eventIdx < sortedData.length && sortedData[eventIdx].time < endTime) {
                const ev = sortedData[eventIdx];
                if (cumulativeCounts[ev.zone_id]) {
                    if (ev.in_count !== undefined) {
                        cumulativeCounts[ev.zone_id].in = ev.in_count;
                    }
                    if (ev.out_count !== undefined) {
                        cumulativeCounts[ev.zone_id].out = ev.out_count;
                    }
                }
                eventIdx++;
            }

            const bucket: Record<string, number | string> = {
                name: `${i * bucketSize}s`
            };

            // Calculate totals across all line zones
            let totalIn = 0;
            let totalOut = 0;

            lineZones.forEach(z => {
                const lc = lineCrossingData[z.id];
                if (lc) {
                    // Use proportional values based on progress
                    const progress = Math.min(1, endTime / maxTime);
                    totalIn += Math.round(lc.in * progress);
                    totalOut += Math.round(lc.out * progress);
                }
            });

            bucket.entries = totalIn;
            bucket.exits = totalOut;
            bucket.net = totalIn - totalOut;

            timeline.push(bucket);
        }

        return timeline;
    }, [detectionData, lineCrossingData, zones, duration]);

    if (!lineCrossingData || Object.keys(lineCrossingData).length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No line crossing data available
            </div>
        );
    }

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart
                    data={chartData}
                    margin={{
                        top: 20,
                        right: 10,
                        left: -10,
                        bottom: 5,
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke={ANALYTICS_COLORS.grid} vertical={false} />
                    <XAxis
                        dataKey="name"
                        stroke={ANALYTICS_COLORS.axis}
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        tick={{ dy: 5 }}
                    />
                    <YAxis
                        stroke={ANALYTICS_COLORS.axis}
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                    />
                    <Legend
                        iconType="circle"
                        verticalAlign="top"
                        align="right"
                        wrapperStyle={{ fontSize: '10px', paddingBottom: '8px', top: 0, right: 0 }}
                    />
                    <ReferenceLine y={0} stroke="#555" strokeDasharray="3 3" />
                    <Line
                        type="monotone"
                        dataKey="entries"
                        name="↓ Cumulative Entries"
                        stroke={ANALYTICS_COLORS.positive}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="exits"
                        name="↑ Cumulative Exits"
                        stroke={ANALYTICS_COLORS.negative}
                        strokeWidth={2}
                        dot={false}
                        isAnimationActive={false}
                    />
                    <Line
                        type="monotone"
                        dataKey="net"
                        name="Net Flow"
                        stroke={ANALYTICS_COLORS.primary}
                        strokeWidth={2}
                        strokeDasharray="5 5"
                        dot={false}
                        isAnimationActive={false}
                    />
                    <Tooltip
                        contentStyle={CHART_STYLES.tooltip}
                        itemStyle={CHART_STYLES.tooltipItem}
                        labelStyle={CHART_STYLES.tooltipLabel}
                        allowEscapeViewBox={{ x: false, y: true }}
                        wrapperStyle={{ zIndex: 100 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    );
}
