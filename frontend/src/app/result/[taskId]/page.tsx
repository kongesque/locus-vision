"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/utils/api";
import { COCO_CLASSES } from "@/utils/types";
import { LoadingOverlay } from "@/components/layout";
import { Download, FileJson, Table, Clock, Users, Activity, BarChart3, Flame, Info, TrendingUp, Layers, Timer, ArrowLeftRight, PieChart, MousePointerClick, Monitor, Cpu, Calendar, Play } from "lucide-react";
import { BentoGrid, BentoCard } from "@/components/dashboard/BentoGrid";
import DashboardCard from "@/components/dashboard/DashboardCard";
import ActivityTimeline from "@/components/dashboard/ActivityTimeline";
import DwellTimeChart from "@/components/dashboard/DwellTimeChart";
import PeakTimeChart from "@/components/dashboard/PeakTimeChart";
import HeatmapChart from "@/components/dashboard/HeatmapChart";
import Sparkline from "@/components/dashboard/Sparkline";
import ZoneComparisonChart from "@/components/dashboard/ZoneComparisonChart";
import OccupancyStackedChart from "@/components/dashboard/OccupancyStackedChart";
import DwellDistributionChart from "@/components/dashboard/DwellDistributionChart";
import TrafficFlowChart from "@/components/dashboard/TrafficFlowChart";
import CumulativeFlowChart from "@/components/dashboard/CumulativeFlowChart";
import BounceRateChart from "@/components/dashboard/BounceRateChart";
import ClassBreakdownChart from "@/components/dashboard/ClassBreakdownChart";
import ZoneDistributionChart from "@/components/dashboard/ZoneDistributionChart";

export default function ResultPage() {
    const params = useParams();

    const router = useRouter();
    const taskId = params.taskId as string;

    const [isHeatmapEnabled, setIsHeatmapEnabled] = useState(false);

    const { data: job, isLoading } = useQuery({
        queryKey: ["job", taskId],
        queryFn: () => api.getJob(taskId),
        enabled: !!taskId,
        refetchInterval: (query) => {
            // Poll while processing
            if (query.state.data?.status === "processing") {
                return 1000;
            }
            return false;
        },
    });

    if (isLoading) {
        return <LoadingOverlay message="Loading results..." />;
    }

    if (!job) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <p className="text-secondary-text">Job not found</p>
            </div>
        );
    }

    if (job.status === "processing") {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="flex flex-col items-center">
                    <div className="relative w-24 h-24 mb-4">
                        <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
                            <circle
                                className="stroke-gray-400/20"
                                cx="50"
                                cy="50"
                                r="42"
                                fill="none"
                                strokeWidth="6"
                            />
                            <circle
                                className="stroke-text-color transition-all duration-300"
                                cx="50"
                                cy="50"
                                r="42"
                                fill="none"
                                strokeWidth="6"
                                strokeLinecap="round"
                                strokeDasharray="264"
                                strokeDashoffset={264 - (job.progress / 100) * 264}
                            />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <span className="text-xl font-medium text-text-color tabular-nums">
                                {job.progress}
                            </span>
                        </div>
                    </div>
                    <p className="text-lg font-medium text-text-color">
                        Processing<span className="animate-pulse">...</span>
                    </p>
                </div>
            </div>
        );
    }

    const videoUrl = api.getOutputVideoUrl(taskId);

    // Calculate zone statistics
    const zoneStats: Record<string, { total: number; peak: number }> = {};
    job.detectionData?.forEach((event) => {
        const zoneId = event.zone_id;
        if (!zoneStats[zoneId]) {
            zoneStats[zoneId] = { total: 0, peak: 0 };
        }
        zoneStats[zoneId].total = event.count;
        if (event.count > zoneStats[zoneId].peak) {
            zoneStats[zoneId].peak = event.count;
        }
    });

    // Calculate zone-wise totals and Grand Total
    const zoneCounts: Record<string, number> = {};
    let grandTotal = 0;

    if (job.zones) {
        job.zones.forEach(zone => {
            const label = zone.label || `Zone ${zone.id}`;
            if (!zoneCounts[label]) zoneCounts[label] = 0;

            const isLine = zone.points?.length === 2;
            if (isLine) {
                // For lines, use Total Activity (In + Out)
                const lc = job.lineCrossingData?.[zone.id];
                if (lc) {
                    const totalCrossings = lc.in + lc.out;
                    zoneCounts[label] += totalCrossings;
                    grandTotal += totalCrossings;
                }
            } else {
                // For zones, use Unique Visitors
                const zoneDwells = job.dwellData?.filter(d => d.zone_id === zone.id);
                if (zoneDwells) {
                    zoneCounts[label] += zoneDwells.length;
                    grandTotal += zoneDwells.length;
                }
            }
        });
    }

    // Calculate per-class totals from latest detection events
    const perClassTotals: Record<number, number> = {};
    job.detectionData?.forEach((event: any) => {
        if (event.class_counts) {
            Object.entries(event.class_counts).forEach(([classId, count]) => {
                const cls = parseInt(classId);
                perClassTotals[cls] = Math.max(perClassTotals[cls] || 0, count as number);
            });
        }
    });

    return (
        <main className="h-full w-full overflow-auto bg-background text-text-color p-4">
            <div className="flex flex-col gap-4 min-h-full">
                {/* Row 1: Video + Analytics */}
                <div className="grid grid-cols-12 gap-4">
                    {/* Main Video Tile - Spans 8 cols, aspect-video forces 16:9 height */}
                    <BentoCard
                        className="col-span-8 aspect-video p-0"
                        title={job.name || "Video Feed"}
                        icon={<div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />}
                        noScroll
                        noSpacer
                        darkHeader
                    >
                        <div className="relative w-full h-full bg-black flex items-center justify-center group">
                            <video
                                src={videoUrl}
                                controls
                                className="w-full h-full object-contain"
                                muted
                            />
                            {/* Heatmap Overlay */}
                            {isHeatmapEnabled && (
                                <div className="absolute inset-0 pointer-events-none z-10">
                                    <HeatmapChart
                                        data={job.heatmapData}
                                        zones={job.zones}
                                        overlay={true}
                                        videoWidth={job.frameWidth}
                                        videoHeight={job.frameHeight}
                                    />
                                </div>
                            )}

                        </div>
                    </BentoCard>

                    {/* Analytics Cards - Top Right (4 cols, matches video height) */}
                    <div className="col-span-4 relative">
                        <BentoCard
                            className="!absolute inset-0"
                            title="Analytics"
                            headerAction={
                                <button
                                    onClick={() => setIsHeatmapEnabled(!isHeatmapEnabled)}
                                    className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all ${isHeatmapEnabled
                                        ? "bg-orange-500/20 text-orange-500 border border-orange-500/30"
                                        : "bg-btn-bg text-secondary-text border border-primary-border hover:bg-btn-hover"
                                        }`}
                                    title="Toggle Heatmap Overlay"
                                >
                                    <Flame className="w-3 h-3" />
                                    Heatmap
                                </button>
                            }
                        >
                            <div className="space-y-2 px-2 pb-4 pt-1">
                                {/* Video Info Card (Context first) */}
                                <div className="bg-card-bg rounded-md p-3">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Info className="w-3.5 h-3.5 text-blue-400" />
                                        <span className="text-xs font-semibold text-text-color tracking-tight uppercase">Video Environment</span>
                                    </div>

                                    <div className="grid grid-cols-1 gap-4">
                                        {/* Group 1: Source & Metadata */}
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-1.5 mb-1.5">
                                                <Monitor className="w-3 h-3 text-secondary-text" />
                                                <span className="text-[10px] font-bold text-secondary-text uppercase tracking-widest">Metadata</span>
                                            </div>
                                            <div className="space-y-1.5 text-xs">
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Duration</span>
                                                    <span className="font-mono text-text-color">
                                                        {(() => {
                                                            const duration = Math.max(...(job.detectionData?.map(d => d.time) || [0]), 0);
                                                            return duration >= 60
                                                                ? `${Math.floor(duration / 60)}m ${(duration % 60).toFixed(0)}s`
                                                                : `${duration.toFixed(1)}s`;
                                                        })()}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Resolution</span>
                                                    <span className="font-mono text-text-color">{job.frameWidth} × {job.frameHeight}</span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Source</span>
                                                    <span className={`px-1.5 py-0.5 rounded-sm text-[10px] font-medium leading-none ${job.sourceType === 'rtsp' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                                                        job.sourceType === 'webcam' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                                                            'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                                        }`}>
                                                        {job.sourceType === 'rtsp' ? 'RTSP STREAM' :
                                                            job.sourceType === 'webcam' ? 'WEBCAM' :
                                                                'LOCAL FILE'}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Engine</span>
                                                    <span className="px-1.5 py-0.5 rounded-sm bg-btn-bg text-secondary-text text-[10px] font-mono border border-primary-border uppercase">
                                                        {job.model?.replace('.pt', '') || "YOLOv8"}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Confidence</span>
                                                    <span className="font-mono text-text-color">
                                                        {(job.confidence > 1 ? job.confidence : job.confidence * 100).toFixed(0)}%
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-start h-auto min-h-4 py-0.5">
                                                    <span className="text-secondary-text">Target Classes</span>
                                                    <div className="flex flex-wrap gap-1 justify-end max-w-[60%]">
                                                        {(() => {
                                                            // Get unique class IDs from all zones
                                                            const uniqueClassIds = new Set<number>();
                                                            job.zones?.forEach(zone => {
                                                                zone.classIds?.forEach(classId => uniqueClassIds.add(classId));
                                                            });
                                                            const sortedClassIds = Array.from(uniqueClassIds).sort((a, b) => a - b);

                                                            return sortedClassIds.map(classId => (
                                                                <span
                                                                    key={classId}
                                                                    className="px-1.5 py-0.5 rounded-sm text-[9px] font-medium leading-none bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                                                >
                                                                    {COCO_CLASSES[classId] || `Class ${classId}`}
                                                                </span>
                                                            ));
                                                        })()}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Group 2: Activity Summary */}
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-1.5 mb-1.5">
                                                <Activity className="w-3 h-3 text-secondary-text" />
                                                <span className="text-[10px] font-bold text-secondary-text uppercase tracking-widest">Activity Summary</span>
                                            </div>
                                            <div className="space-y-1.5 text-xs">
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Total Events</span>
                                                    <span className="font-mono text-text-color font-bold">{grandTotal}</span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Peak Occupancy</span>
                                                    <span className="font-mono text-amber-400 font-bold">
                                                        {Math.max(...Object.values(zoneStats).map(s => s.peak), 0)}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Avg Dwell</span>
                                                    <span className="font-mono text-text-color">
                                                        {(() => {
                                                            const allDwell = job.dwellData || [];
                                                            if (allDwell.length === 0) return "—";
                                                            const avgDwell = allDwell.reduce((acc, d) => acc + d.duration, 0) / allDwell.length;
                                                            return `${avgDwell.toFixed(1)}s`;
                                                        })()}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Active Zones</span>
                                                    <span className="font-mono text-text-color">
                                                        {job.zones?.length || 0}
                                                    </span>
                                                </div>
                                                {/* Per-Class Breakdown */}
                                                {Object.keys(perClassTotals).length > 0 && (
                                                    <div className="flex justify-between items-start h-auto min-h-4 py-0.5">
                                                        <span className="text-secondary-text">Class Breakdown</span>
                                                        <div className="flex flex-wrap gap-1 justify-end max-w-[60%]">
                                                            {Object.entries(perClassTotals)
                                                                .sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
                                                                .map(([classId, count]) => (
                                                                    <span
                                                                        key={classId}
                                                                        className="px-1.5 py-0.5 rounded-sm text-[9px] font-medium leading-none bg-green-500/10 text-green-400 border border-green-500/20"
                                                                        title={`${COCO_CLASSES[parseInt(classId)]}: ${count} detected`}
                                                                    >
                                                                        {count} {COCO_CLASSES[parseInt(classId)] || `Class ${classId}`}
                                                                    </span>
                                                                ))}
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Footer Metadata */}
                                        <div className="pt-2 border-t border-white/5 space-y-1.5">
                                            <div className="flex justify-between items-center">
                                                <span className="text-[10px] text-secondary-text flex items-center gap-1"><Clock className="w-2.5 h-2.5" /> Runtime</span>
                                                <span className="text-[10px] font-mono text-secondary-text italic">
                                                    {job.processTime && job.processTime >= 60
                                                        ? `${Math.floor(job.processTime / 60)}m ${(job.processTime % 60).toFixed(0)}s`
                                                        : `${job.processTime?.toFixed(1)}s`}
                                                </span>
                                            </div>
                                            <div className="flex justify-between items-center">
                                                <span className="text-[10px] text-secondary-text flex items-center gap-1"><Calendar className="w-2.5 h-2.5" /> Processed On</span>
                                                <span className="text-[10px] text-secondary-text/80">
                                                    {job.createdAt ? new Date(job.createdAt).toLocaleDateString('en-US', {
                                                        month: 'short',
                                                        day: 'numeric',
                                                        hour: '2-digit',
                                                        minute: '2-digit'
                                                    }) : '—'}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Activity Card */}
                                <DashboardCard
                                    title="Activity Timeline"
                                    icon={<Activity className="w-3.5 h-3.5 text-blue-400" />}
                                    tooltip="Visualizes detection frequency over the video duration."
                                    contentClassName="h-[100px]"
                                >
                                    <ActivityTimeline
                                        data={job.detectionData}
                                        zones={job.zones}
                                        duration={job.processTime}
                                    />
                                </DashboardCard>

                                {/* Zone Comparison */}
                                <DashboardCard
                                    title="Zone Overview"
                                    icon={<BarChart3 className="w-3.5 h-3.5 text-blue-400" />}
                                    tooltip="Compare total visitors, peak occupancy, and average dwell time across zones."
                                    contentClassName="h-[150px]"
                                >
                                    <ZoneComparisonChart
                                        detectionData={job.detectionData}
                                        dwellData={job.dwellData}
                                        zones={job.zones}
                                    />
                                </DashboardCard>

                                {/* Cumulative Flow Chart */}
                                <DashboardCard
                                    title="Net Flow Over Time"
                                    icon={<TrendingUp className="w-3.5 h-3.5 text-green-400" />}
                                    tooltip="Tracks the cumulative difference between entries and exits over time."
                                    contentClassName="h-[120px]"
                                >
                                    <CumulativeFlowChart
                                        detectionData={job.detectionData}
                                        lineCrossingData={job.lineCrossingData}
                                        zones={job.zones}
                                        duration={job.processTime}
                                    />
                                </DashboardCard>

                                {/* Traffic Flow */}
                                <DashboardCard
                                    title="Entry / Exit"
                                    icon={<ArrowLeftRight className="w-3.5 h-3.5 text-purple-400" />}
                                    tooltip="Total count of objects entering vs. exiting the zones."
                                    contentClassName="h-[150px] overflow-hidden"
                                >
                                    <TrafficFlowChart
                                        lineCrossingData={job.lineCrossingData}
                                        zones={job.zones}
                                    />
                                </DashboardCard>

                                {/* Occupancy Stacked */}
                                <DashboardCard
                                    title="Zone Loads"
                                    icon={<Layers className="w-3.5 h-3.5 text-indigo-400" />}
                                    tooltip="Shows how occupancy is distributed across zones at any given time."
                                    contentClassName="h-[120px]"
                                >
                                    <OccupancyStackedChart
                                        data={job.detectionData}
                                        zones={job.zones}
                                        duration={job.processTime}
                                    />
                                </DashboardCard>



                                {/* Dwell Distribution */}
                                <DashboardCard
                                    title="Dwell Segments"
                                    icon={<Timer className="w-3.5 h-3.5 text-amber-400" />}
                                    tooltip="Categorizes visits based on their duration."
                                    contentClassName="h-[140px]"
                                >
                                    <DwellDistributionChart data={job.dwellData} zones={job.zones} />
                                </DashboardCard>

                                {/* Bounce Rate */}
                                <DashboardCard
                                    title="Bounce Rate"
                                    icon={<MousePointerClick className="w-3.5 h-3.5 text-red-400" />}
                                    tooltip="Percentage of visits shorter than 5 seconds (fleeting detections)."
                                    contentClassName="h-[200px]"
                                >
                                    <BounceRateChart
                                        dwellData={job.dwellData}
                                        zones={job.zones}
                                    />
                                </DashboardCard>

                                {/* Zone Distribution */}
                                <DashboardCard
                                    title="Zone Distribution"
                                    icon={<PieChart className="w-3.5 h-3.5 text-cyan-400" />}
                                    tooltip="Proportion of visitors distributed across zones."
                                    contentClassName="h-[180px]"
                                >
                                    <ZoneDistributionChart
                                        dwellData={job.dwellData}
                                        zones={job.zones}
                                    />
                                </DashboardCard>

                                {/* Class Breakdown */}
                                <DashboardCard
                                    title="Class Distribution"
                                    icon={<PieChart className="w-3.5 h-3.5 text-pink-400" />}
                                    tooltip="Proportion of different object classes detected."
                                    contentClassName="h-[180px]"
                                >
                                    <ClassBreakdownChart zones={job.zones} detectionData={job.detectionData} />
                                </DashboardCard>
                            </div>
                        </BentoCard>
                    </div>
                </div>

                {/* Row 2: Zone Analysis + Actions */}
                <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
                    {/* Zone Analysis - Bottom Left (8 cols) */}
                    <BentoCard
                        className="col-span-8 min-h-0"
                    >
                        <div className="grid grid-cols-3 gap-3 px-2 py-2 h-full">
                            {job.zones?.map((zone) => {
                                const stats = zoneStats[zone.id] || { total: 0, peak: 0 };
                                const isLine = zone.points?.length === 2;
                                const lineCrossing = job.lineCrossingData?.[zone.id];

                                const zoneDwellEvents = job.dwellData?.filter(d => d.zone_id === zone.id) || [];
                                const totalDwell = zoneDwellEvents.reduce((acc, curr) => acc + curr.duration, 0);
                                const avgDwell = zoneDwellEvents.length > 0 ? (totalDwell / zoneDwellEvents.length).toFixed(1) : "0.0";

                                return (
                                    <div
                                        key={zone.id}
                                        className="bg-card-bg hover:bg-card-bg-hover rounded-md p-2 transition-colors group"
                                    >
                                        <div className="flex items-center justify-between mb-2">
                                            <div className="flex items-center gap-2">
                                                <div
                                                    className="w-2 h-2 rounded-full"
                                                    style={{ backgroundColor: `rgb(${zone.color?.join(",")})` }}
                                                />
                                                <span className="text-sm font-medium text-text-color/90 truncate max-w-[100px]">
                                                    {zone.label}
                                                </span>
                                            </div>
                                            {/* Multi-class indicator */}
                                            {zone.classIds && zone.classIds.length > 1 && (
                                                <span className="text-[9px] px-1.5 py-0.5 rounded-sm bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                                    {zone.classIds.length} classes
                                                </span>
                                            )}
                                        </div>

                                        <div className="mb-2 h-10 opacity-60 group-hover:opacity-100 transition-opacity">
                                            <Sparkline
                                                data={job.detectionData}
                                                zoneId={zone.id}
                                                classId={zone.classIds[0]}
                                                duration={job.processTime || 10}
                                            />
                                        </div>

                                        {isLine && lineCrossing ? (
                                            <div className="space-y-2">
                                                <div className="flex items-end justify-between">
                                                    <div>
                                                        <p className="text-[10px] text-secondary-text uppercase tracking-wider mb-0.5">Net Flow</p>
                                                        <div className={`text-lg font-bold leading-none ${lineCrossing.in - lineCrossing.out > 0 ? 'text-green-400' : lineCrossing.in - lineCrossing.out < 0 ? 'text-red-400' : 'text-text-color'}`}>
                                                            {lineCrossing.in - lineCrossing.out > 0 ? '+' : ''}{lineCrossing.in - lineCrossing.out}
                                                        </div>
                                                    </div>
                                                    <div className="text-right text-xs text-secondary-text">
                                                        <span>In: <span className="text-green-400 font-medium">{lineCrossing.in}</span></span>
                                                        <span className="ml-2">Out: <span className="text-red-400 font-medium">{lineCrossing.out}</span></span>
                                                    </div>
                                                </div>
                                                {/* Line Crossing Per-Class breakdown (from last event) */}
                                                {(() => {
                                                    const zoneEvents = job.detectionData?.filter(e => e.zone_id === zone.id) || [];
                                                    const lastEvent = zoneEvents[zoneEvents.length - 1];
                                                    const classCounts = lastEvent?.class_counts;
                                                    if (!classCounts || Object.keys(classCounts).length === 0) return null;

                                                    return (
                                                        <div className="flex flex-wrap gap-1 mt-1 pt-1 border-t border-white/5">
                                                            {Object.entries(classCounts).map(([clsId, count]) => (
                                                                <span key={clsId} className="px-1 py-0.5 rounded-[2px] text-[8px] bg-blue-500/10 text-blue-400/80 border border-blue-500/10">
                                                                    {count} {COCO_CLASSES[parseInt(clsId)]}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        ) : (
                                            <div className="space-y-2">
                                                <div className="flex items-end justify-between">
                                                    <div>
                                                        <p className="text-[10px] text-secondary-text uppercase tracking-wider mb-0.5">Visitors</p>
                                                        <p className="text-2xl font-bold text-text-color leading-none">
                                                            {stats.total}
                                                        </p>
                                                    </div>
                                                    <div className="text-right">
                                                        <p className="text-[10px] text-secondary-text uppercase tracking-wider mb-0.5">Avg Time</p>
                                                        <span className="text-sm font-medium text-amber-500/90">
                                                            {avgDwell}s
                                                        </span>
                                                    </div>
                                                </div>
                                                {/* Zone Per-Class breakdown (from last event) */}
                                                {(() => {
                                                    const zoneEvents = job.detectionData?.filter(e => e.zone_id === zone.id) || [];
                                                    const lastEvent = zoneEvents[zoneEvents.length - 1];
                                                    const classCounts = lastEvent?.class_counts;
                                                    if (!classCounts || Object.keys(classCounts).length === 0) return null;

                                                    return (
                                                        <div className="flex flex-wrap gap-1 mt-1 pt-1 border-t border-white/5">
                                                            {Object.entries(classCounts).map(([clsId, count]) => (
                                                                <span key={clsId} className="px-1 py-0.5 rounded-[2px] text-[8px] bg-green-500/10 text-green-400/80 border border-green-500/10">
                                                                    {count} {COCO_CLASSES[parseInt(clsId)]}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </BentoCard>

                    {/* Control Panel / Actions - Spans 4 cols, fills remaining height */}
                    <BentoCard className="col-span-4" noScroll>
                        <div className="flex flex-col h-full px-2 justify-center gap-3 text-text-color">

                            {/* Primary Action */}
                            <a
                                href={videoUrl}
                                download={`video-${taskId}.mp4`}
                                className="w-full py-3 flex items-center justify-center gap-2 rounded-lg bg-text-color text-bg-color hover:opacity-90 text-sm font-bold transition-all group shadow-sm"
                            >
                                <Download className="w-4 h-4 group-hover:scale-110 transition-transform" />
                                Download Video
                            </a>

                            {/* Secondary Actions Row */}
                            <div className="flex gap-2">
                                <a
                                    href={api.getExportCsvUrl(taskId)}
                                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-btn-bg hover:bg-btn-hover border border-primary-border text-xs font-medium transition-all text-text-color shadow-sm"
                                    download
                                >
                                    <Table className="w-3.5 h-3.5 opacity-70" /> CSV Export
                                </a>
                                <a
                                    href={api.getExportJsonUrl(taskId)}
                                    className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg bg-btn-bg hover:bg-btn-hover border border-primary-border text-xs font-medium transition-all text-text-color shadow-sm"
                                    download
                                >
                                    <FileJson className="w-3.5 h-3.5 opacity-70" /> JSON Export
                                </a>
                            </div>

                            {/* Edit Action */}
                            <button
                                onClick={() => router.push(`/zone/${taskId}`)}
                                className="w-full py-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 text-xs font-medium transition-all"
                            >
                                Edit Zones & Configuration
                            </button>
                        </div>
                    </BentoCard>
                </div>


            </div >
        </main >
    );
}
