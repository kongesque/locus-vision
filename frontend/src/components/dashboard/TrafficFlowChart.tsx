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
    Cell,
    ReferenceLine
} from "recharts";
import { Zone, LineCrossing } from "@/utils/types";

interface TrafficFlowChartProps {
    lineCrossingData: Record<string, LineCrossing>;
    zones: Zone[];
}

export default function TrafficFlowChart({ lineCrossingData, zones }: TrafficFlowChartProps) {
    const chartData = useMemo(() => {
        if (!lineCrossingData || Object.keys(lineCrossingData).length === 0) return [];

        return zones
            .filter(zone => lineCrossingData[zone.id]) // Only zones with line crossing data
            .map(zone => {
                const lc = lineCrossingData[zone.id];
                const netFlow = lc.in - lc.out;
                return {
                    name: zone.label.length > 10 ? zone.label.substring(0, 10) + '...' : zone.label,
                    fullName: zone.label,
                    id: zone.id,
                    in: lc.in,
                    out: -lc.out, // Negative for visual effect
                    outAbs: lc.out,
                    net: netFlow,
                    color: zone.color,
                    classCount: zone.classIds?.length || 1
                };
            });
    }, [lineCrossingData, zones]);

    if (!lineCrossingData || Object.keys(lineCrossingData).length === 0) {
        return (
            <div className="flex h-full items-center justify-center text-secondary-text text-sm">
                No line crossing data available
            </div>
        );
    }

    const maxValue = Math.max(
        ...chartData.map(d => Math.max(d.in, d.outAbs))
    );

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
                        domain={[-maxValue * 1.1, maxValue * 1.1]}
                        tickFormatter={(value) => Math.abs(value).toString()}
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
                        formatter={((value: number | undefined, name: string | undefined) => {
                            const absValue = Math.abs(value ?? 0);
                            return [absValue, name === 'in' ? '↓ Entries' : '↑ Exits'];
                        }) as never}
                        labelFormatter={(label, payload) => {
                            const data = payload?.[0]?.payload;
                            const fullName = data?.fullName || label;
                            const classCount = data?.classCount || 1;
                            return classCount > 1 ? `${fullName} (${classCount} classes)` : fullName;
                        }}
                    // allowEscapeViewBox={{ x: false, y: true }}
                    />
                    <Legend
                        iconType="circle"
                        verticalAlign="top"
                        align="right"
                        wrapperStyle={{ fontSize: '10px', paddingBottom: '8px', top: 0, right: 0 }}
                        formatter={(value) => value === 'in' ? '↓ Entries' : '↑ Exits'}
                    />
                    <ReferenceLine x={0} stroke="#555" strokeWidth={1} />
                    <Bar dataKey="in" name="in" fill="#22c55e" radius={[0, 4, 4, 0]} barSize={12} isAnimationActive={false} />
                    <Bar dataKey="out" name="out" fill="#ef4444" radius={[4, 0, 0, 4]} barSize={12} isAnimationActive={false} />
                </BarChart>
            </ResponsiveContainer>
            {/* Net Flow Summary */}
            <div className="flex justify-center gap-4 mt-2 text-xs">
                {chartData.map(d => (
                    <div key={d.id} className="flex items-center gap-1">
                        <div
                            className="w-2 h-2 rounded-full"
                            style={{ backgroundColor: `rgb(${d.color?.join(",")})` }}
                        />
                        <span className="text-secondary-text">{d.name}:</span>
                        <span className={`font-medium ${d.net > 0 ? 'text-green-400' : d.net < 0 ? 'text-red-400' : 'text-text-color'}`}>
                            {d.net > 0 ? '+' : ''}{d.net}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
