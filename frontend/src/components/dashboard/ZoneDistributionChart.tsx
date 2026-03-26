"use client";

import { useMemo } from "react";
import {
    PieChart,
    Pie,
    Cell,
    Tooltip,
    ResponsiveContainer
} from "recharts";
import { DwellEvent, Zone } from "@/utils/types";
import { CLASS_COLORS, DEFAULT_COLOR } from "@/utils/colors";

interface ZoneDistributionChartProps {
    dwellData: DwellEvent[];
    zones: Zone[];
}

export default function ZoneDistributionChart({ dwellData, zones }: ZoneDistributionChartProps) {
    const chartData = useMemo(() => {
        if (!dwellData || dwellData.length === 0 || !zones || zones.length === 0) {
            return [];
        }

        // Count unique visitors per zone based on dwell events
        const zoneCounts: Record<string, number> = {};
        zones.forEach(zone => {
            zoneCounts[zone.id] = 0;
        });

        dwellData.forEach(event => {
            if (zoneCounts[event.zone_id] !== undefined) {
                zoneCounts[event.zone_id]++;
            }
        });

        // Build chart data using CLASS_COLORS based on zone's classId
        return zones
            .map(zone => ({
                name: zone.label,
                id: zone.id,
                value: zoneCounts[zone.id] || 0,
                color: CLASS_COLORS[zone.classIds[0]] || DEFAULT_COLOR
            }))
            .filter(item => item.value > 0)
            .sort((a, b) => b.value - a.value);
    }, [dwellData, zones]);

    if (!dwellData || dwellData.length === 0 || chartData.length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No zone data available
            </div>
        );
    }

    return (
        <div className="h-full w-full relative flex items-center justify-center">
            {/* Legend on the left - Absolute positioned to center the chart itself */}
            <div className="absolute left-0 top-1/2 -translate-y-1/2 flex flex-col justify-center gap-y-1 text-[10px] z-10 pl-1">
                {chartData.map(item => (
                    <div key={item.id} className="flex items-center gap-1">
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
                            formatter={((value: number | undefined) => [`${value ?? 0} visitor${(value ?? 0) !== 1 ? 's' : ''}`, 'Count']) as never}
                            allowEscapeViewBox={{ x: false, y: true }}
                            wrapperStyle={{ zIndex: 100 }}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
