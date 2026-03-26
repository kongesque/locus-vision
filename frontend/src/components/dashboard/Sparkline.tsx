"use client";

import { useMemo } from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import { DetectionEvent } from "@/utils/types";
import { CLASS_COLORS, DEFAULT_COLOR } from "@/utils/colors";

interface SparklineProps {
    data: DetectionEvent[];
    zoneId: string;
    classId: number;
    duration: number;
}

export default function Sparkline({ data, zoneId, classId, duration }: SparklineProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        // Downsample for sparkline (approx 20 points)
        const points = 20;
        const bucketSize = duration / points;
        const timeline = [];

        for (let i = 0; i < points; i++) {
            const startTime = i * bucketSize;
            const endTime = (i + 1) * bucketSize;
            // Max count in this bucket for this zone
            let maxCount = 0;

            // Filter events in this time range for this zone
            const eventsInBucket = data.filter(e =>
                e.zone_id === zoneId &&
                e.time >= startTime &&
                e.time < endTime
            );

            if (eventsInBucket.length > 0) {
                maxCount = Math.max(...eventsInBucket.map(e => e.count));
            }

            timeline.push({ i, val: maxCount });
        }

        return timeline;
    }, [data, zoneId, duration]);

    if (chartData.length === 0) return null;

    // Use CLASS_COLORS based on classId
    const zoneColor = CLASS_COLORS[classId] || DEFAULT_COLOR;

    return (
        <div className="h-8 w-full opacity-50">
            <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                    <defs>
                        <linearGradient id={`spark-${zoneId}`} x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor={zoneColor} stopOpacity={0.5} />
                            <stop offset="95%" stopColor={zoneColor} stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <Area
                        type="monotone"
                        dataKey="val"
                        stroke={zoneColor}
                        strokeWidth={1}
                        fill={`url(#spark-${zoneId})`}
                        isAnimationActive={false}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
}
