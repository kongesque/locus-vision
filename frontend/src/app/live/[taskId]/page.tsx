"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/utils/api";
import { LoadingOverlay } from "@/components/layout";
import { Square, Play, Info, Monitor, Activity, Clock, Settings, RefreshCw, Users, TrendingUp, ArrowUp, ArrowDown } from "lucide-react";
import { BentoCard } from "@/components/dashboard/BentoGrid";
import DashboardCard from "@/components/dashboard/DashboardCard";

export default function LivePage() {
    const params = useParams();
    const router = useRouter();
    const taskId = params.taskId as string;

    const [isRunning, setIsRunning] = useState(true);
    const isRunningRef = useRef(true); // Ref to avoid stale closure in WS callbacks
    const [counts, setCounts] = useState<Record<string, number>>({});
    const [connectionStatus, setConnectionStatus] = useState<
        "connecting" | "live" | "stopped"
    >("connecting");
    const wsRef = useRef<WebSocket | null>(null);
    const [frame, setFrame] = useState<string | null>(null);
    const [isStreamReady, setIsStreamReady] = useState(false);
    const retryCountRef = useRef(0);
    const maxRetries = 3;
    const [startTime] = useState<Date>(new Date());
    const [elapsedTime, setElapsedTime] = useState(0);

    const { data: job, isLoading, refetch } = useQuery({
        queryKey: ["job", taskId],
        queryFn: () => api.getJob(taskId),
        enabled: !!taskId,
        // Refetch periodically while stream is running to sync zone data
        refetchInterval: isRunning ? 3000 : false,
        staleTime: 1000,
        refetchOnMount: "always",
    });

    // Elapsed time counter
    useEffect(() => {
        if (!isRunning || connectionStatus !== "live") return;

        const interval = setInterval(() => {
            setElapsedTime(Math.floor((Date.now() - startTime.getTime()) / 1000));
        }, 1000);

        return () => clearInterval(interval);
    }, [isRunning, connectionStatus, startTime]);

    // WebSocket connection for live stream with retry logic
    useEffect(() => {
        if (!taskId || !isRunning) return;

        const connectWebSocket = () => {
            // Check ref before connecting (ref has current value, not stale closure)
            if (!isRunningRef.current) return;

            const ws = new WebSocket(api.getWebSocketUrl(taskId));
            wsRef.current = ws;

            ws.onopen = () => {
                setConnectionStatus("live");
                retryCountRef.current = 0; // Reset retry count on successful connection
                // Refetch job data to ensure zones are up to date
                refetch();
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === "frame") {
                        setFrame(`data:image/jpeg;base64,${data.frame}`);
                        setIsStreamReady(true);
                    }
                    if (data.counts) {
                        setCounts(data.counts);
                    }
                    // Handle error messages from backend - stop on fatal errors
                    if (data.error) {
                        console.error("Stream error:", data.error);
                        // Stop reconnection attempts on fatal errors
                        isRunningRef.current = false;
                        setIsRunning(false);
                        setConnectionStatus("stopped");
                        if (wsRef.current) {
                            wsRef.current.close();
                            wsRef.current = null;
                        }
                    }
                } catch {
                    // Handle raw frame data
                    if (event.data instanceof Blob) {
                        const url = URL.createObjectURL(event.data);
                        setFrame(url);
                        setIsStreamReady(true);
                    }
                }
            };

            ws.onerror = () => {
                // Check ref for current running state (avoids stale closure)
                if (!isRunningRef.current) {
                    setConnectionStatus("stopped");
                    return;
                }
                // Don't immediately mark as stopped, try to reconnect
                if (retryCountRef.current < maxRetries) {
                    retryCountRef.current++;
                    setTimeout(connectWebSocket, 1000); // Retry after 1 second
                } else {
                    setConnectionStatus("stopped");
                    setIsRunning(false);
                    isRunningRef.current = false;
                }
            };

            ws.onclose = () => {
                // Use ref to check current running state (avoids stale closure)
                if (!isRunningRef.current) {
                    // User stopped or error occurred - don't reconnect
                    setConnectionStatus("stopped");
                    return;
                }
                // Only reconnect if we haven't exhausted retries
                if (retryCountRef.current < maxRetries) {
                    retryCountRef.current++;
                    setTimeout(connectWebSocket, 1000);
                } else {
                    setConnectionStatus("stopped");
                    setIsRunning(false);
                    isRunningRef.current = false;
                }
            };
        };

        connectWebSocket();

        return () => {
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
        };
    }, [taskId, isRunning]);

    // Poll for counts as fallback (don't immediately stop on first poll)
    useEffect(() => {
        if (!taskId || !isRunning) return;

        let pollCount = 0;
        const pollCounts = async () => {
            try {
                const data = await api.getLiveCounts(taskId);
                setCounts(data.counts);
                // Only stop if stream reports not running AND we've polled a few times
                // This gives time for the backend to start
                if (!data.running && pollCount > 5) {
                    setIsRunning(false);
                    setConnectionStatus("stopped");
                }
                pollCount++;
            } catch {
                // Ignore errors
            }
        };

        const interval = setInterval(pollCounts, 1000);
        return () => clearInterval(interval);
    }, [taskId, isRunning]);

    const handleStop = async () => {
        try {
            // Set ref FIRST to prevent reconnection attempts
            isRunningRef.current = false;

            // Close WebSocket immediately
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }

            // Update state
            setIsRunning(false);
            setConnectionStatus("stopped");

            // Tell backend to stop
            await api.stopLiveStream(taskId);
        } catch (error) {
            console.error("Failed to stop stream:", error);
        }
    };

    const handleRestart = () => {
        // Reset ref first
        isRunningRef.current = true;
        retryCountRef.current = 0;
        setConnectionStatus("connecting");
        setIsRunning(true);
    };

    const formatTime = (seconds: number) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Calculate total count across all zones
    const totalCount = Object.values(counts).reduce((sum, count) => sum + count, 0);

    if (isLoading) {
        return <LoadingOverlay message="Loading stream..." />;
    }

    if (!job) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <p className="text-secondary-text">Stream not found</p>
            </div>
        );
    }

    // Show loader until stream is ready (first frame received)
    if (!isStreamReady && isRunning) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="flex flex-col items-center">
                    <p className="text-lg font-medium text-text-color">
                        Connecting<span className="animate-pulse">...</span>
                    </p>
                    <span className="text-base text-secondary-text mt-1">
                        {job.sourceType === "webcam" ? "Opening webcam" : "Connecting to RTSP stream"}
                    </span>
                </div>
            </div>
        );
    }

    return (
        <main className="h-full w-full overflow-auto bg-background text-text-color p-4">
            <div className="flex flex-col gap-4 min-h-full">
                {/* Row 1: Video + Live Stats */}
                <div className="grid grid-cols-12 gap-4">
                    {/* Main Video Tile - Spans 8 cols */}
                    <BentoCard
                        className="col-span-8 aspect-video p-0"
                        title="Live Feed"
                        icon={
                            <div className={`w-2 h-2 rounded-full ${connectionStatus === "live"
                                ? "bg-green-500 animate-pulse"
                                : connectionStatus === "connecting"
                                    ? "bg-yellow-500 animate-pulse"
                                    : "bg-gray-500"
                                }`} />
                        }
                        noScroll
                        noSpacer
                        darkHeader
                        headerAction={
                            <div className="flex items-center gap-2">
                                <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${connectionStatus === "live"
                                    ? "bg-green-500/20 text-green-400 border border-green-500/30"
                                    : connectionStatus === "connecting"
                                        ? "bg-yellow-500/20 text-yellow-400 border border-yellow-500/30"
                                        : "bg-gray-500/20 text-gray-400 border border-gray-500/30"
                                    }`}>
                                    {connectionStatus === "live" ? "LIVE" : connectionStatus === "connecting" ? "CONNECTING" : "STOPPED"}
                                </span>
                            </div>
                        }
                    >
                        <div className="relative w-full h-full bg-black flex items-center justify-center">
                            {frame ? (
                                <img
                                    src={frame}
                                    alt="Live stream"
                                    className="w-full h-full object-contain"
                                />
                            ) : (
                                <div className="text-secondary-text flex flex-col items-center gap-2">
                                    <div className="w-12 h-12 rounded-full bg-gray-800 flex items-center justify-center">
                                        <Play className="w-6 h-6 text-gray-500" />
                                    </div>
                                    <span>
                                        {connectionStatus === "connecting"
                                            ? "Connecting to stream..."
                                            : "Stream stopped"}
                                    </span>
                                </div>
                            )}

                            {/* Elapsed Time Overlay */}
                            {connectionStatus === "live" && (
                                <div className="absolute bottom-3 left-3 flex items-center gap-2 px-2.5 py-1 rounded-md bg-black/60 backdrop-blur-sm">
                                    <Clock className="w-3 h-3 text-white/70" />
                                    <span className="text-xs font-mono text-white/90">{formatTime(elapsedTime)}</span>
                                </div>
                            )}
                        </div>
                    </BentoCard>

                    {/* Live Stats - Right Sidebar (4 cols) */}
                    <div className="col-span-4 relative">
                        <BentoCard
                            className="!absolute inset-0"
                            title="Live Analytics"
                            headerAction={
                                <button
                                    onClick={isRunning ? handleStop : handleRestart}
                                    className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium transition-all ${isRunning
                                        ? "bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-red-500/30"
                                        : "bg-green-500/20 text-green-400 border border-green-500/30 hover:bg-green-500/30"
                                        }`}
                                >
                                    {isRunning ? (
                                        <>
                                            <Square className="w-3 h-3" />
                                            Stop
                                        </>
                                    ) : (
                                        <>
                                            <RefreshCw className="w-3 h-3" />
                                            Restart
                                        </>
                                    )}
                                </button>
                            }
                        >
                            <div className="space-y-2 px-2 pb-4 pt-1">
                                {/* Stream Info Card */}
                                <div className="bg-card-bg rounded-md p-3">
                                    <div className="flex items-center gap-2 mb-3">
                                        <Info className="w-3.5 h-3.5 text-blue-400" />
                                        <span className="text-xs font-semibold text-text-color tracking-tight uppercase">Stream Info</span>
                                    </div>

                                    <div className="space-y-2">
                                        {/* Metadata */}
                                        <div className="space-y-2">
                                            <div className="flex items-center gap-1.5 mb-1.5">
                                                <Monitor className="w-3 h-3 text-secondary-text" />
                                                <span className="text-[10px] font-bold text-secondary-text uppercase tracking-widest">Connection</span>
                                            </div>
                                            <div className="space-y-1.5 text-xs">
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
                                                    <span className="text-secondary-text">Resolution</span>
                                                    <span className="font-mono text-text-color">{job.frameWidth} × {job.frameHeight}</span>
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
                                                <div className="flex justify-between items-center h-4">
                                                    <span className="text-secondary-text">Session Time</span>
                                                    <span className="font-mono text-text-color">{formatTime(elapsedTime)}</span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Total Activity Summary */}
                                <DashboardCard
                                    title="Total Activity"
                                    icon={<Activity className="w-3.5 h-3.5 text-blue-400" />}
                                    tooltip="Total count of all detections across all zones."
                                    contentClassName="h-[60px]"
                                >
                                    <div className="flex items-center justify-center h-full">
                                        <div className="text-center">
                                            <p className="text-4xl font-bold text-text-color tabular-nums">{totalCount}</p>
                                            <p className="text-[10px] text-secondary-text uppercase tracking-wider mt-1">Total Detections</p>
                                        </div>
                                    </div>
                                </DashboardCard>

                                {/* Zone Counts */}
                                <DashboardCard
                                    title="Zone Breakdown"
                                    icon={<Users className="w-3.5 h-3.5 text-green-400" />}
                                    tooltip="Real-time count per zone."
                                    contentClassName="max-h-[280px] overflow-y-auto"
                                >
                                    <div className="space-y-2">
                                        {job.zones?.map((zone) => {
                                            const count = counts[zone.id] || 0;
                                            const isLine = zone.points?.length === 2;

                                            return (
                                                <div
                                                    key={zone.id}
                                                    className="bg-btn-bg/50 border border-primary-border rounded-lg p-3 hover:bg-btn-hover transition-colors"
                                                >
                                                    <div className="flex items-center justify-between">
                                                        <div className="flex items-center gap-2">
                                                            <div
                                                                className="w-2.5 h-2.5 rounded-full"
                                                                style={{
                                                                    backgroundColor: `rgb(${zone.color?.join(",")})`,
                                                                }}
                                                            />
                                                            <span className="text-sm font-medium text-text-color">
                                                                {zone.label}
                                                            </span>
                                                            <span className="text-[10px] text-secondary-text px-1.5 py-0.5 rounded bg-btn-bg border border-primary-border">
                                                                {isLine ? "Line" : "Zone"}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            {count > 0 && (
                                                                <TrendingUp className="w-3 h-3 text-green-400" />
                                                            )}
                                                            <span className="text-xl font-bold text-text-color tabular-nums">
                                                                {count}
                                                            </span>
                                                        </div>
                                                    </div>
                                                    <p className="text-[10px] text-secondary-text mt-1">
                                                        {isLine ? "Crossings detected" : "Currently in zone"}
                                                    </p>
                                                </div>
                                            );
                                        })}

                                        {(!job.zones || job.zones.length === 0) && (
                                            <div className="text-center py-4 text-secondary-text text-sm">
                                                No zones configured
                                            </div>
                                        )}
                                    </div>
                                </DashboardCard>
                            </div>
                        </BentoCard>
                    </div>
                </div>

                {/* Row 2: Zone Analysis Cards + Actions */}
                <div className="flex-1 grid grid-cols-12 gap-4 min-h-0">
                    {/* Zone Cards - Bottom Left (8 cols) */}
                    <BentoCard className="col-span-8 min-h-0">
                        <div className="grid grid-cols-3 gap-3 px-2 py-2 h-full">
                            {job.zones?.map((zone) => {
                                const count = counts[zone.id] || 0;
                                const isLine = zone.points?.length === 2;

                                return (
                                    <div
                                        key={zone.id}
                                        className="bg-card-bg hover:bg-card-bg-hover rounded-md p-3 transition-colors group flex flex-col"
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
                                            {connectionStatus === "live" && (
                                                <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                                            )}
                                        </div>

                                        {/* Live Count Visual */}
                                        <div className="flex-1 flex items-center justify-center py-2">
                                            <div className="text-center">
                                                <p className="text-4xl font-bold text-text-color tabular-nums leading-none">
                                                    {count}
                                                </p>
                                                <p className="text-[10px] text-secondary-text uppercase tracking-wider mt-1">
                                                    {isLine ? "Crossings" : "In Zone"}
                                                </p>
                                            </div>
                                        </div>

                                        {/* Zone Type Badge */}
                                        <div className="mt-auto pt-2 border-t border-white/5">
                                            <div className="flex items-center justify-between text-[10px]">
                                                <span className="text-secondary-text">Type</span>
                                                <span className={`px-1.5 py-0.5 rounded-sm font-medium ${isLine
                                                    ? "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                                                    : "bg-blue-500/10 text-blue-400 border border-blue-500/20"
                                                    }`}>
                                                    {isLine ? "LINE" : "ZONE"}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}

                            {(!job.zones || job.zones.length === 0) && (
                                <div className="col-span-3 flex items-center justify-center text-secondary-text">
                                    <div className="text-center">
                                        <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                        <p className="text-sm">No zones configured</p>
                                        <p className="text-xs mt-1">Edit zones to start tracking</p>
                                    </div>
                                </div>
                            )}
                        </div>
                    </BentoCard>

                    {/* Control Panel - Spans 4 cols */}
                    <BentoCard className="col-span-4" noScroll>
                        <div className="flex flex-col h-full px-2 justify-center gap-3 text-text-color">

                            {/* Primary Action - Stop/Start */}
                            <button
                                onClick={isRunning ? handleStop : handleRestart}
                                className={`w-full py-3 flex items-center justify-center gap-2 rounded-lg text-sm font-bold transition-all group shadow-sm ${isRunning
                                    ? "bg-red-500 text-white hover:bg-red-600"
                                    : "bg-green-500 text-white hover:bg-green-600"
                                    }`}
                            >
                                {isRunning ? (
                                    <>
                                        <Square className="w-4 h-4 group-hover:scale-110 transition-transform" />
                                        Stop Stream
                                    </>
                                ) : (
                                    <>
                                        <RefreshCw className="w-4 h-4 group-hover:scale-110 transition-transform" />
                                        Restart Stream
                                    </>
                                )}
                            </button>

                            {/* Edit Zones */}
                            <button
                                onClick={() => router.push(`/zone/${taskId}`)}
                                className="w-full py-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/20 text-xs font-medium transition-all flex items-center justify-center gap-2"
                            >
                                <Settings className="w-3.5 h-3.5" />
                                Edit Zones & Configuration
                            </button>

                            {/* New Session */}
                            <button
                                onClick={() => router.push("/")}
                                className="w-full py-2 rounded-lg bg-btn-bg hover:bg-btn-hover border border-primary-border text-xs font-medium transition-all text-text-color flex items-center justify-center gap-2"
                            >
                                <Play className="w-3.5 h-3.5" />
                                New Session
                            </button>
                        </div>
                    </BentoCard>
                </div>
            </div>
        </main>
    );
}
