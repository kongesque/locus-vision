"use client";

import { useState, useCallback, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/utils/api";
import { ZoneCanvas, ZoneSidebar } from "@/components/zone";
import { LoadingOverlay } from "@/components/layout";
import type { Zone, Point, TrackerConfig } from "@/utils/types";

function generateZoneId(): string {
    return `zone_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function getColorFromClassId(classId: number): [number, number, number] {
    const hue = ((classId * 137.508) % 360) / 360;
    const s = 0.85;
    const l = 0.55;

    // HSL to RGB conversion
    const c = (1 - Math.abs(2 * l - 1)) * s;
    const x = c * (1 - Math.abs(((hue * 6) % 2) - 1));
    const m = l - c / 2;

    let r = 0, g = 0, b = 0;
    if (hue < 1 / 6) { r = c; g = x; b = 0; }
    else if (hue < 2 / 6) { r = x; g = c; b = 0; }
    else if (hue < 3 / 6) { r = 0; g = c; b = x; }
    else if (hue < 4 / 6) { r = 0; g = x; b = c; }
    else if (hue < 5 / 6) { r = x; g = 0; b = c; }
    else { r = c; g = 0; b = x; }

    return [
        Math.round((r + m) * 255),
        Math.round((g + m) * 255),
        Math.round((b + m) * 255),
    ];
}

export default function ZonePage() {
    const params = useParams();
    const router = useRouter();
    const taskId = params.taskId as string;

    // Fetch job data
    const { data: job, isLoading } = useQuery({
        queryKey: ["job", taskId],
        queryFn: () => api.getJob(taskId),
        enabled: !!taskId,
    });

    // State
    const [zones, setZones] = useState<Zone[]>([]);
    const [activeZoneId, setActiveZoneId] = useState<string | null>(null);
    // Detection mode
    const [detectionMode, setDetectionMode] = useState<'zone' | 'frame'>('zone');
    const [frameClassIds, setFrameClassIds] = useState<number[]>([0]); // For frame-wide mode
    // Configuration
    const maxPoints = 12; // High default for flexible polygon drawing
    const [confidence, setConfidence] = useState(35);
    const [model, setModel] = useState("yolo11n.pt");
    const [trackerConfig, setTrackerConfig] = useState<TrackerConfig>({
        track_high_thresh: 0.45,
        track_low_thresh: 0.1,
        match_thresh: 0.8,
        track_buffer: 30,
    });
    const [frameSize, setFrameSize] = useState({ width: 0, height: 0 });
    const [isProcessing, setIsProcessing] = useState(false);
    const [progress, setProgress] = useState(0);

    // Initialize settings from job
    useEffect(() => {
        if (!job) return;

        // Initialize zones
        if (job.zones && job.zones.length > 0) {
            setZones(job.zones);
            setActiveZoneId(job.zones[0].id);
        } else {
            const initialZone: Zone = {
                id: generateZoneId(),
                points: [],
                classIds: [0], // Default: person
                color: getColorFromClassId(0),
                label: "Zone 1",
            };
            setZones([initialZone]);
            setActiveZoneId(initialZone.id);
        }

        // Initialize parameters
        if (job.confidence) setConfidence(job.confidence);
        if (job.model) setModel(job.model);
        if (job.trackerConfig) setTrackerConfig(job.trackerConfig);

        // Initialize frame size from job data (important for frame-wide mode)
        if (job.frameWidth && job.frameHeight) {
            setFrameSize({ width: job.frameWidth, height: job.frameHeight });
        }
    }, [job]);

    const handleFrameLoaded = useCallback((width: number, height: number) => {
        setFrameSize({ width, height });
    }, []);

    const handlePointAdded = useCallback((zoneId: string, point: Point) => {
        setZones((prev) =>
            prev.map((zone) => {
                if (zone.id === zoneId && zone.points.length < maxPoints) {
                    return { ...zone, points: [...zone.points, point] };
                }
                return zone;
            })
        );
    }, [maxPoints]);

    // Auto-create a new zone with the first point already added (for click-to-create UX)
    // If firstPoint is {x: -1, y: -1}, create empty zone (used for closing current polygon)
    const handleAutoCreateZone = useCallback((firstPoint: Point) => {
        const newZone: Zone = {
            id: generateZoneId(),
            points: firstPoint.x >= 0 && firstPoint.y >= 0 ? [firstPoint] : [],
            classIds: [0], // Default: person
            color: getColorFromClassId(0),
            label: `Zone ${zones.length + 1}`,
        };
        setZones((prev) => [...prev, newZone]);
        setActiveZoneId(newZone.id);
    }, [zones.length]);

    const handleZoneDelete = useCallback((zoneId: string) => {
        setZones((prev) => {
            const filtered = prev.filter((z) => z.id !== zoneId);
            // If we deleted the active zone, select another
            if (activeZoneId === zoneId && filtered.length > 0) {
                setActiveZoneId(filtered[0].id);
            } else if (filtered.length === 0) {
                setActiveZoneId(null);
            }
            return filtered;
        });
    }, [activeZoneId]);

    const handleZoneClassChange = useCallback((zoneId: string, classIds: number[]) => {
        setZones((prev) =>
            prev.map((zone) => {
                if (zone.id === zoneId) {
                    return { ...zone, classIds, color: getColorFromClassId(classIds[0]) };
                }
                return zone;
            })
        );
    }, []);

    const handleZoneLabelChange = useCallback((zoneId: string, label: string) => {
        setZones((prev) =>
            prev.map((zone) => (zone.id === zoneId ? { ...zone, label } : zone))
        );
    }, []);

    const handleProcess = useCallback(async () => {
        let zonesToProcess: Zone[];

        if (detectionMode === 'frame') {
            // Frame-wide mode: Create synthetic zone covering entire frame
            // Use job dimensions directly to ensure correct size
            const width = job?.frameWidth || frameSize.width || 1920;
            const height = job?.frameHeight || frameSize.height || 1080;

            const syntheticZone: Zone = {
                id: 'global',
                points: [
                    { x: 0, y: 0 },
                    { x: width, y: 0 },
                    { x: width, y: height },
                    { x: 0, y: height }
                ],
                classIds: frameClassIds,
                color: getColorFromClassId(frameClassIds[0]),
                label: 'Global Detection'
            };
            zonesToProcess = [syntheticZone];
        } else {
            // Zone-based mode: Use regular zones
            const completeZones = zones.filter((z) => z.points.length >= 2);
            if (completeZones.length === 0) return;
            zonesToProcess = completeZones;
        }

        // Check if this is a live stream (RTSP/webcam)
        const isLiveStream = job?.sourceType === "rtsp" || job?.sourceType === "webcam";

        // Only show loader for file uploads, not for live streams
        if (!isLiveStream) {
            setIsProcessing(true);
        }

        try {
            const response = await api.processJob(taskId, {
                zones: zonesToProcess,
                confidence,
                model,
                trackerConfig,
            });

            // For live streams only: redirect immediately to /live page (no loader)
            if (isLiveStream && response.redirect) {
                router.push(response.redirect);
                return;
            }

            // For file uploads: poll for progress, then redirect to /result
            const pollProgress = async () => {
                try {
                    const data = await api.getProgress(taskId);
                    setProgress(data.progress);

                    if (data.status === "completed") {
                        router.push(`/result/${taskId}`);
                    } else if (data.status === "error") {
                        setIsProcessing(false);
                        alert("Processing failed. Please try again.");
                    } else {
                        setTimeout(pollProgress, 500);
                    }
                } catch {
                    setTimeout(pollProgress, 1000);
                }
            };

            setTimeout(pollProgress, 1000);
        } catch (error) {
            console.error("Failed to start processing:", error);
            setIsProcessing(false);
        }
    }, [zones, confidence, model, trackerConfig, taskId, router, job?.sourceType, detectionMode, frameClassIds, frameSize]);

    if (isLoading) {
        return <LoadingOverlay message="Loading..." />;
    }

    if (isProcessing) {
        return (
            <div className="flex-1 flex items-center justify-center">
                <div className="flex flex-col items-center">
                    {/* Circular Progress */}
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
                                strokeDashoffset={264 - (progress / 100) * 264}
                            />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                            <span className="text-xl font-medium text-text-color tabular-nums">
                                {progress}
                            </span>
                        </div>
                    </div>
                    <p className="text-lg font-medium text-text-color">
                        Processing video<span className="animate-pulse">...</span>
                    </p>
                    <span className="text-base text-secondary-text">
                        Analyzing frames and detecting objects
                    </span>
                </div>
            </div>
        );
    }

    const frameUrl = job?.framePath
        ? api.getMediaUrl(job.framePath.replace("uploads/", ""))
        : "";

    return (
        <main className="flex-1 flex items-center justify-center p-3 overflow-hidden">
            <div className="flex flex-col md:flex-row w-full h-full gap-4 md:gap-6">
                {/* Sidebar */}
                <ZoneSidebar
                    zones={zones}
                    activeZoneId={activeZoneId}
                    confidence={confidence}
                    model={model}
                    trackerConfig={trackerConfig}
                    detectionMode={detectionMode}
                    frameClassIds={frameClassIds}
                    onDetectionModeChange={setDetectionMode}
                    onFrameClassIdsChange={setFrameClassIds}
                    onZoneSelect={setActiveZoneId}
                    onZoneDelete={handleZoneDelete}
                    onZoneClassChange={handleZoneClassChange}
                    onZoneLabelChange={handleZoneLabelChange}
                    onConfidenceChange={setConfidence}
                    onModelChange={setModel}
                    onTrackerConfigChange={setTrackerConfig}
                    onProcess={handleProcess}
                    isProcessing={isProcessing}
                />

                {/* Canvas - Conditional based on detection mode */}
                {detectionMode === 'zone' ? (
                    <ZoneCanvas
                        frameUrl={frameUrl}
                        zones={zones}
                        activeZoneId={activeZoneId}
                        maxPoints={maxPoints}
                        onZonesChange={setZones}
                        onPointAdded={handlePointAdded}
                        onFrameLoaded={handleFrameLoaded}
                        onZoneSelect={setActiveZoneId}
                        onAutoCreateZone={handleAutoCreateZone}
                    />
                ) : (
                    <div className="flex-1 flex items-center justify-center p-4 bg-primary-color border border-primary-border rounded-xl overflow-hidden relative">
                        {frameUrl && (
                            <img
                                src={frameUrl}
                                alt="Frame preview"
                                className="absolute inset-0 w-full h-full object-contain opacity-20 p-4"
                            />
                        )}
                        <div className="relative z-10 flex flex-col items-center justify-center text-center p-8">
                            <h3 className="text-2xl font-bold text-text-color mb-2">
                                Frame-Wide Detection
                            </h3>
                            <p className="text-secondary-text max-w-md">
                                Detecting <span className="text-blue-400 font-semibold">{frameClassIds.length} class{frameClassIds.length > 1 ? 'es' : ''}</span> across the entire video frame
                            </p>
                        </div>
                    </div>
                )}
            </div>


        </main>
    );
}
