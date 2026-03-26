"use client";

import { useMemo } from "react";
import {
    PieChart,
    Pie,
    Cell,
    Tooltip,
    ResponsiveContainer
} from "recharts";
import { Zone, DetectionEvent } from "@/utils/types";
import { COCO_CLASSES } from "@/utils/types";
import { CLASS_COLORS, DEFAULT_COLOR } from "@/utils/colors"; // Use shared colors

interface ClassBreakdownChartProps {
    zones: Zone[];
    detectionData?: DetectionEvent[];
}

export default function ClassBreakdownChart({ zones, detectionData }: ClassBreakdownChartProps) {
    const chartData = useMemo(() => {
        if (!zones || zones.length === 0) return [];

        const classCounts: Record<number, number> = {};

        // If we have actual detection data, use it
        if (detectionData && detectionData.length > 0) {
            // Calculate totals from the last event for each zone
            zones.forEach(zone => {
                const zoneEvents = detectionData.filter(e => e.zone_id === zone.id);
                const lastEvent = zoneEvents[zoneEvents.length - 1];

                if (lastEvent?.class_counts) {
                    Object.entries(lastEvent.class_counts).forEach(([clsId, count]) => {
                        const id = parseInt(clsId);
                        classCounts[id] = (classCounts[id] || 0) + (count as number);
                    });
                } else if (lastEvent?.count) {
                    // Fallback for old data or single class: assume all correspond to first configured class
                    const mainClassId = zone.classIds[0];
                    classCounts[mainClassId] = (classCounts[mainClassId] || 0) + lastEvent.count;
                }
            });
        }

        // If no data found (or empty), check if we want to show "Targeted Classes" instead (fallback)
        // But usually for "Results", showing 0 is better than showing config if we have processed data.
        // Let's fallback only if detectionData is undefined (not just empty filtered result)
        if (Object.keys(classCounts).length === 0 && (!detectionData || detectionData.length === 0)) {
            // Fallback: Count zones by class ID (support multi-class per zone) - what we had before
            zones.forEach(zone => {
                zone.classIds.forEach(classId => {
                    classCounts[classId] = (classCounts[classId] || 0) + 1;
                });
            });
        }

        // Convert to chart data
        return Object.entries(classCounts).map(([classId, count]) => {
            const id = parseInt(classId);
            return {
                name: COCO_CLASSES[id] || `Class ${id}`,
                value: count,
                classId: id,
                color: CLASS_COLORS[id] || DEFAULT_COLOR
            };
        }).sort((a, b) => b.value - a.value);
    }, [zones, detectionData]);

    if (!zones || zones.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No zones defined
            </div>
        );
    }

    return (
        <div className="h-full w-full relative flex items-center justify-center">
            {/* Legend on the left - Absolute positioned to center the chart itself */}
            <div className="absolute left-0 top-1/2 -translate-y-1/2 flex flex-col justify-center gap-y-1 text-[10px] z-10 pl-1">
                {chartData.map(item => (
                    <div key={item.classId} className="flex items-center gap-1">
                        <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ backgroundColor: item.color }} />
                        <span className="text-secondary-text whitespace-nowrap">{item.name}: {item.value}</span>
                    </div>
                ))}
            </div>

            {/* Chart container */}
            <div className="flex-1 h-full min-w-0">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
                        <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={35}
                            outerRadius={60}
                            paddingAngle={2}
                            dataKey="value"
                            nameKey="name"
                            label={(props: any) => {
                                const { cx, x, y, percent, name } = props;
                                return (
                                    <text
                                        x={x}
                                        y={y}
                                        fill="#999"
                                        fontSize={10}
                                        className="z-10"
                                        textAnchor={x > cx ? 'start' : 'end'}
                                        dominantBaseline="central"
                                    >
                                        {`${name ?? ''} ${((percent ?? 0) * 100).toFixed(0)}%`}
                                    </text>
                                );
                            }}
                            labelLine={false}
                            isAnimationActive={false}
                        >
                            {chartData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{ backgroundColor: '#111', borderColor: '#333', borderRadius: '8px', fontSize: '12px' }}
                            itemStyle={{ color: '#fff' }}
                            formatter={((value: number | undefined) => [`${value ?? 0} zone${(value ?? 0) !== 1 ? 's' : ''}`, 'Count']) as never}
                            allowEscapeViewBox={{ x: false, y: true }}
                            wrapperStyle={{ zIndex: 100 }}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
