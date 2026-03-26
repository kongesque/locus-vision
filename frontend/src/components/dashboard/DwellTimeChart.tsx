"use client";

import { useMemo } from "react";
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
    Legend
} from "recharts";
import { DwellEvent, Zone } from "@/utils/types";

interface DwellTimeChartProps {
    data: DwellEvent[];
    zones: Zone[];
}

export default function DwellTimeChart({ data, zones }: DwellTimeChartProps) {
    const chartData = useMemo(() => {
        if (!data || data.length === 0) return [];

        const zoneStats: Record<string, { totalDuration: number; count: number }> = {};

        // Initialize with all zones
        zones.forEach(z => {
            zoneStats[z.id] = { totalDuration: 0, count: 0 };
        });

        // specific dwell event is already duration in seconds
        data.forEach(event => {
            if (zoneStats[event.zone_id]) {
                zoneStats[event.zone_id].totalDuration += event.duration;
                zoneStats[event.zone_id].count += 1;
            }
        });

        return zones.map(zone => {
            const stats = zoneStats[zone.id];
            return {
                name: zone.label,
                id: zone.id,
                avgDwell: stats.count > 0 ? Number((stats.totalDuration / stats.count).toFixed(1)) : 0,
                color: zone.color
            };
        });
    }, [data, zones]);

    if (!data || data.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No dwell data available
            </div>
        );
    }

    return (
        <div className="h-full w-full overflow-hidden">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{
                        top: 5,
                        right: 0,
                        left: -35,
                        bottom: 5,
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={true} vertical={false} />
                    <XAxis
                        type="number"
                        stroke="#666"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        unit="s"
                    />
                    <YAxis
                        dataKey="name"
                        type="category"
                        stroke="#666"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        width={80}
                    />
                    <Tooltip
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                        contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px', fontSize: '12px' }}
                        itemStyle={{ color: '#fff' }}
                        labelStyle={{ color: '#999', marginBottom: '4px' }}
                        formatter={(value: number | undefined) => [`${value || 0}s`, 'Avg Dwell Time']}
                    />
                    <Legend
                        iconType="circle"
                        verticalAlign="top"
                        align="right"
                        wrapperStyle={{ fontSize: '10px', paddingBottom: '10px', top: 0, right: 0 }}
                    />
                    <Bar dataKey="avgDwell" radius={[0, 4, 4, 0]} barSize={20} isAnimationActive={false}>
                        {chartData.map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={`rgb(${entry.color.join(",")})`} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
