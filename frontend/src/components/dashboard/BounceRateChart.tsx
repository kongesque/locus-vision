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
    Cell
} from "recharts";
import { DwellEvent, Zone } from "@/utils/types";

interface BounceRateChartProps {
    dwellData: DwellEvent[];
    zones: Zone[];
    bounceThreshold?: number; // Seconds considered as "bounce" (default: 5)
}

export default function BounceRateChart({ dwellData, zones, bounceThreshold = 5 }: BounceRateChartProps) {
    const chartData = useMemo(() => {
        if (!dwellData || dwellData.length === 0 || !zones || zones.length === 0) return [];

        return zones.map(zone => {
            const zoneEvents = dwellData.filter(d => d.zone_id === zone.id);
            const totalVisits = zoneEvents.length;
            const bounces = zoneEvents.filter(d => d.duration < bounceThreshold).length;
            const bounceRate = totalVisits > 0 ? Math.round((bounces / totalVisits) * 100) : 0;
            const engagedRate = 100 - bounceRate;

            return {
                name: zone.label.length > 10 ? zone.label.substring(0, 10) + '...' : zone.label,
                fullName: zone.label,
                id: zone.id,
                bounceRate: bounceRate,
                engagedRate: engagedRate,
                bounces: bounces,
                engaged: totalVisits - bounces,
                total: totalVisits,
                color: zone.color,
                classCount: zone.classIds?.length || 1
            };
        }).filter(d => d.total > 0); // Only show zones with data
    }, [dwellData, zones, bounceThreshold]);

    if (!dwellData || dwellData.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No dwell data available
            </div>
        );
    }

    if (chartData.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No zone visits recorded
            </div>
        );
    }

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={chartData}
                    layout="vertical"
                    margin={{
                        top: 20,
                        right: 30,
                        left: 0,
                        bottom: 5,
                    }}
                >
                    <CartesianGrid strokeDasharray="3 3" stroke="#333" horizontal={false} />
                    <XAxis
                        type="number"
                        stroke="#666"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        domain={[0, 100]}
                        unit="%"
                    />
                    <YAxis
                        dataKey="name"
                        type="category"
                        stroke="#666"
                        fontSize={10}
                        tickLine={false}
                        axisLine={false}
                        width={70}
                    />
                    <Tooltip
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                        contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px', fontSize: '12px' }}
                        itemStyle={{ color: '#fff' }}
                        labelStyle={{ color: '#999', marginBottom: '4px' }}
                        formatter={((value: number | undefined, name: string | undefined, props: { payload: { bounces: number; engaged: number; total: number; fullName: string } }) => {
                            const p = props.payload;
                            if (name === 'Bounce') {
                                return [`${value}% (${p.bounces}/${p.total} visitors)`, 'Bounce Rate'];
                            }
                            return [`${value}% (${p.engaged}/${p.total} visitors)`, 'Engaged Rate'];
                        }) as never}
                        labelFormatter={(label, payload) => {
                            const data = payload?.[0]?.payload;
                            const fullName = data?.fullName || label;
                            const classCount = data?.classCount || 1;
                            return classCount > 1 ? `${fullName} (${classCount} classes)` : fullName;
                        }}
                    />
                    <Bar dataKey="engagedRate" name="Engaged" stackId="a" fill="#22c55e" radius={[0, 0, 0, 0]} barSize={16} isAnimationActive={false} />
                    <Bar dataKey="bounceRate" name="Bounce" stackId="a" fill="#ef4444" radius={[0, 4, 4, 0]} barSize={16} isAnimationActive={false} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
