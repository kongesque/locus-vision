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
    Legend,
    Cell
} from "recharts";
import { DetectionEvent, DwellEvent, Zone, COCO_CLASSES } from "@/utils/types";

interface ZoneComparisonChartProps {
    detectionData: DetectionEvent[];
    dwellData: DwellEvent[];
    zones: Zone[];
}

export default function ZoneComparisonChart({ detectionData, dwellData, zones }: ZoneComparisonChartProps) {
    const chartData = useMemo(() => {
        if (!zones || zones.length === 0) return [];

        return zones.map(zone => {
            // Calculate peak from detection data
            let peak = 0;
            detectionData?.forEach(event => {
                if (event.zone_id === zone.id && event.count > peak) {
                    peak = event.count;
                }
            });

            // Get last count as total visitors
            const zoneEvents = detectionData?.filter(e => e.zone_id === zone.id) || [];
            const lastEvent = zoneEvents[zoneEvents.length - 1];
            const totalVisitors = lastEvent?.count || 0;
            const classBreakdown = lastEvent?.class_counts || {};

            // Calculate avg dwell from dwell data
            const zoneDwellEvents = dwellData?.filter(d => d.zone_id === zone.id) || [];
            const totalDwell = zoneDwellEvents.reduce((acc, curr) => acc + curr.duration, 0);
            const avgDwell = zoneDwellEvents.length > 0 ? Number((totalDwell / zoneDwellEvents.length).toFixed(1)) : 0;

            return {
                name: zone.label.length > 12 ? zone.label.substring(0, 12) + '...' : zone.label,
                fullName: zone.label,
                id: zone.id,
                visitors: totalVisitors,
                peak: peak,
                avgDwell: avgDwell,
                color: zone.color,
                classCount: zone.classIds?.length || 1,
                classBreakdown // Pass breakdown to chart data
            };
        });
    }, [detectionData, dwellData, zones]);

    if (!zones || zones.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No zones defined
            </div>
        );
    }

    return (
        <div className="h-full w-full">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart
                    data={chartData}
                    margin={{
                        top: 20,
                        right: 10,
                        left: -10,
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
                        interval={0}
                        tick={{ dy: 5 }}
                    />
                    <YAxis
                        stroke="#666"
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
                    <Bar dataKey="visitors" name="Visitors" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={16} isAnimationActive={false} />
                    <Bar dataKey="peak" name="Peak" fill="#f97316" radius={[4, 4, 0, 0]} barSize={16} isAnimationActive={false} />
                    <Bar dataKey="avgDwell" name="Dwell (s)" fill="#a855f7" radius={[4, 4, 0, 0]} barSize={16} isAnimationActive={false} />
                    <Tooltip
                        cursor={{ fill: 'rgba(255,255,255,0.05)' }}
                        contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px', fontSize: '12px' }}
                        itemStyle={{ color: '#fff' }}
                        labelStyle={{ color: '#999', marginBottom: '4px' }}
                        formatter={((value: number | undefined, name: string | undefined, props: any) => {
                            if (name === 'Dwell (s)') return [`${value ?? 0}s`, 'Avg Dwell'];

                            // For Visitors, show breakdown if available
                            if (name === 'Visitors') {
                                const breakdown = props.payload.classBreakdown;
                                if (breakdown && Object.keys(breakdown).length > 0) {
                                    // We can't render custom JSX here easily in default formatter, so we'll stick to string
                                    // But actually, we might want a Custom Tooltip Component if we want rich content.
                                    // For now, let's keep it simple or format the string cleanly?
                                    // Recharts default tooltip handles array of strings? No.
                                    return [`${value ?? 0}`, 'Total Visitors'];
                                }
                                return [`${value ?? 0}`, 'Total Visitors'];
                            }

                            if (name === 'Peak') return [`${value ?? 0}`, 'Peak Count'];
                            return [value, name];
                        }) as never}
                        content={({ active, payload, label }) => {
                            if (active && payload && payload.length) {
                                const data = payload[0].payload;
                                return (
                                    <div className="bg-[#111] border border-[#333] rounded-lg p-3 text-xs shadow-xl z-50">
                                        <p className="text-[#999] mb-2 font-medium">{data.fullName}</p>
                                        {payload.map((entry: any, index: number) => (
                                            <div key={index} className="flex items-center gap-2 mb-1 last:mb-0">
                                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: entry.color }} />
                                                <span className="text-secondary-text min-w-[60px]">{entry.name}:</span>
                                                <span className="text-text-color font-mono">{entry.value}</span>
                                                {entry.name === 'Visitors' && data.classBreakdown && Object.keys(data.classBreakdown).length > 0 && (
                                                    <div className="ml-2 flex items-center gap-1 border-l border-white/10 pl-2">
                                                        {Object.entries(data.classBreakdown).map(([clsId, count]: [string, any]) => (
                                                            <span key={clsId} className="px-1 py-0.5 bg-white/5 rounded text-[9px] text-[#888]">
                                                                {COCO_CLASSES[parseInt(clsId)] || `C${clsId}`}: {count}
                                                            </span>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        ))}

                                        {/* Dedicated Breakdown Section if multiple classes exist */}
                                        {data.classBreakdown && Object.keys(data.classBreakdown).length > 0 && (
                                            <div className="mt-2 pt-2 border-t border-white/10">
                                                <p className="text-[10px] text-[#666] mb-1">Class Breakdown</p>
                                                <div className="flex flex-wrap gap-1">
                                                    {Object.entries(data.classBreakdown).map(([clsId, count]: [string, any]) => (
                                                        <span key={clsId} className="px-1.5 py-0.5 bg-blue-500/10 border border-blue-500/20 text-blue-400 rounded text-[10px]">
                                                            {COCO_CLASSES[parseInt(clsId)] || `Class ${clsId}`}: {count}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            }
                            return null;
                        }}
                        allowEscapeViewBox={{ x: false, y: true }}
                        wrapperStyle={{ zIndex: 100 }}
                    />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
}
