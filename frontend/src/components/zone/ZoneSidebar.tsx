"use client";

import { Trash2, ChevronDown, Pencil } from "lucide-react";
import type { Zone } from "@/utils/types";
import { COCO_CLASSES } from "@/utils/types";

interface ZoneSidebarProps {
    zones: Zone[];
    activeZoneId: string | null;
    confidence: number;
    model: string;
    trackerConfig: {
        track_high_thresh: number;
        track_low_thresh: number;
        match_thresh: number;
        track_buffer: number;
    };
    detectionMode: 'zone' | 'frame';
    frameClassIds: number[];
    onDetectionModeChange: (mode: 'zone' | 'frame') => void;
    onFrameClassIdsChange: (classIds: number[]) => void;
    onZoneSelect: (zoneId: string) => void;
    onZoneDelete: (zoneId: string) => void;
    onZoneClassChange: (zoneId: string, classIds: number[]) => void;
    onZoneLabelChange: (zoneId: string, label: string) => void;
    onConfidenceChange: (value: number) => void;
    onModelChange: (value: string) => void;
    onTrackerConfigChange: (config: {
        track_high_thresh: number;
        track_low_thresh: number;
        match_thresh: number;
        track_buffer: number;
    }) => void;
    onProcess: () => void;
    isProcessing: boolean;
}

function getColorFromClassId(classId: number): string {
    const hue = ((classId * 137.508) % 360);
    return `hsl(${hue}, 85%, 55%)`;
}

const MODEL_OPTIONS = [
    { value: "yolo11n.pt", label: "YOLO11n (Fastest)", short: "Fastest" },
    { value: "yolo11s.pt", label: "YOLO11s (Fast)", short: "Fast" },
    { value: "yolo11m.pt", label: "YOLO11m (Balanced)", short: "Balanced" },
    { value: "yolo11l.pt", label: "YOLO11l (Accurate)", short: "Accurate" },
    { value: "yolo11x.pt", label: "YOLO11x (Most Accurate)", short: "Most Accurate" },
];

export function ZoneSidebar({
    zones,
    activeZoneId,
    confidence,
    model,
    trackerConfig,
    detectionMode,
    frameClassIds,
    onDetectionModeChange,
    onFrameClassIdsChange,
    onZoneSelect,
    onZoneDelete,
    onZoneClassChange,
    onZoneLabelChange,
    onConfidenceChange,
    onModelChange,
    onTrackerConfigChange,
    onProcess,
    isProcessing,
}: ZoneSidebarProps) {
    const [showAdvanced, setShowAdvanced] = useState(false);

    const selectedModel = MODEL_OPTIONS.find((m) => m.value === model);

    const handleTrackerSliderChange = (
        key: keyof typeof trackerConfig,
        rawValue: number
    ) => {
        const value =
            key === "track_buffer" ? rawValue : rawValue / 100;
        onTrackerConfigChange({
            ...trackerConfig,
            [key]: value,
        });
    };

    const resetTrackerDefaults = () => {
        onTrackerConfigChange({
            track_high_thresh: 0.45,
            track_low_thresh: 0.1,
            match_thresh: 0.8,
            track_buffer: 30,
        });
    };

    const canProcess = detectionMode === 'frame' || zones.some((z) => z.points.length >= 2);

    return (
        <section className="w-full md:w-[280px] shrink-0 p-4 flex flex-col gap-4 md:justify-between order-2 md:order-1 bg-primary-color border border-primary-border rounded-xl">
            <div className="overflow-y-auto max-h-[calc(100vh-200px)]">
                {/* Detection Mode Toggle */}
                <div className="mb-4">
                    <h2 className="text-sm font-semibold text-text-color mb-3">
                        Detection Mode
                    </h2>
                    <div className="flex gap-2">
                        <button
                            onClick={() => onDetectionModeChange('zone')}
                            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all ${detectionMode === 'zone'
                                ? 'bg-blue-500 text-white'
                                : 'bg-btn-bg text-secondary-text hover:bg-btn-hover border border-primary-border'
                                }`}
                        >
                            Zone-Based
                        </button>
                        <button
                            onClick={() => onDetectionModeChange('frame')}
                            className={`flex-1 py-2 px-3 rounded-lg text-xs font-medium transition-all ${detectionMode === 'frame'
                                ? 'bg-blue-500 text-white'
                                : 'bg-btn-bg text-secondary-text hover:bg-btn-hover border border-primary-border'
                                }`}
                        >
                            Frame-Wide
                        </button>
                    </div>
                </div>

                {/* Frame-Wide Class Selector (only shown in frame mode) */}
                {detectionMode === 'frame' && (
                    <div className="mb-4 p-3 rounded-lg bg-card-bg border border-primary-border">
                        <h3 className="text-xs font-semibold text-text-color mb-2">Target Classes</h3>
                        <div className="flex flex-wrap gap-1.5 mb-2">
                            {frameClassIds.map(classId => (
                                <span
                                    key={classId}
                                    className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border"
                                    style={{
                                        backgroundColor: `${getColorFromClassId(classId)}20`,
                                        borderColor: `${getColorFromClassId(classId)}40`,
                                        color: getColorFromClassId(classId)
                                    }}
                                >
                                    {COCO_CLASSES[classId]}
                                    {frameClassIds.length > 1 && (
                                        <button
                                            onClick={() => onFrameClassIdsChange(frameClassIds.filter(id => id !== classId))}
                                            className="ml-0.5 hover:opacity-70"
                                        >
                                            ×
                                        </button>
                                    )}
                                </span>
                            ))}
                        </div>
                        <select
                            className="w-full px-2 py-2 rounded-lg bg-btn-bg border border-primary-border text-xs text-text-color"
                            value=""
                            onChange={(e) => {
                                const newClassId = parseInt(e.target.value);
                                if (!frameClassIds.includes(newClassId)) {
                                    onFrameClassIdsChange([...frameClassIds, newClassId]);
                                }
                            }}
                        >
                            <option value="" disabled>+ Add Class</option>
                            {Object.entries(COCO_CLASSES).map(([idx, className]) => (
                                !frameClassIds.includes(Number(idx)) && (
                                    <option key={idx} value={idx}>
                                        {className}
                                    </option>
                                )
                            ))}
                        </select>
                    </div>
                )}

                {/* Zone Selection (only shown in zone mode) */}
                {detectionMode === 'zone' && (
                    <>
                        <h2 className="text-sm font-semibold text-text-color mb-4">
                            Zone Selection
                        </h2>

                        {/* Zone List */}
                        <div className="space-y-4 mb-4">
                            {zones.map((zone) => (
                                <div
                                    key={zone.id}
                                    className={`p-3 rounded-lg border cursor-pointer transition-all ${activeZoneId === zone.id
                                        ? "border-text-color bg-sidebar-item-hover"
                                        : "border-btn-border hover:border-gray-400"
                                        }`}
                                    onClick={() => onZoneSelect(zone.id)}
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <div
                                                className="w-3 h-3 rounded-full"
                                                style={{ backgroundColor: getColorFromClassId(zone.classIds[0]) }}
                                            />
                                            <input
                                                type="text"
                                                value={zone.label}
                                                onChange={(e) => onZoneLabelChange(zone.id, e.target.value)}
                                                onClick={(e) => e.stopPropagation()}
                                                className="bg-transparent text-sm text-text-color font-medium border-none outline-none w-12"
                                            />
                                            <Pencil className="w-3 h-3 text-secondary-text opacity-50" />
                                        </div>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                onZoneDelete(zone.id);
                                            }}
                                            className="p-1 hover:bg-delete-text/20 rounded text-delete-text"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>

                                    <div className="space-y-2">
                                        <span className="text-xs text-secondary-text">Target Classes:</span>

                                        {/* Selected Classes as Tags */}
                                        <div className="flex flex-wrap gap-1.5">
                                            {zone.classIds.map((classId) => (
                                                <div
                                                    key={classId}
                                                    className="group flex items-center gap-1 px-2 py-0.5 rounded bg-btn-bg border border-btn-border text-xs text-text-color"
                                                >
                                                    <span>{COCO_CLASSES[classId]?.charAt(0).toUpperCase() + COCO_CLASSES[classId]?.slice(1)}</span>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            const newClassIds = zone.classIds.filter(id => id !== classId);
                                                            if (newClassIds.length > 0) {
                                                                onZoneClassChange(zone.id, newClassIds);
                                                            }
                                                        }}
                                                        className="opacity-50 hover:opacity-100 hover:text-delete-text transition-opacity"
                                                    >
                                                        ×
                                                    </button>
                                                </div>
                                            ))}
                                        </div>

                                        {/* Add Class Dropdown */}
                                        <select
                                            value=""
                                            onChange={(e) => {
                                                const newClassId = Number(e.target.value);
                                                if (!zone.classIds.includes(newClassId)) {
                                                    onZoneClassChange(zone.id, [...zone.classIds, newClassId]);
                                                }
                                                e.target.value = ""; // Reset
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                            className="w-full bg-btn-bg text-text-color text-xs border border-dashed border-btn-border rounded px-2 py-1.5"
                                        >
                                            <option value="" disabled>+ Add Class</option>
                                            {Object.entries(COCO_CLASSES)
                                                .sort((a, b) => a[1].localeCompare(b[1]))
                                                .filter(([id]) => !zone.classIds.includes(Number(id)))
                                                .map(([id, name]) => (
                                                    <option key={id} value={id}>
                                                        {name.charAt(0).toUpperCase() + name.slice(1)}
                                                    </option>
                                                ))}
                                        </select>
                                    </div>

                                    <div className="text-xs text-secondary-text mt-2">
                                        {zone.points.length} points
                                        {zone.points.length === 2 && " (Line)"}
                                        {zone.points.length >= 3 && " (Polygon)"}
                                    </div>
                                </div>
                            ))}
                        </div>

                    </>
                )}

                <div className="space-y-4">
                    {/* Confidence Slider */}
                    <div>
                        <div className="flex justify-between text-sm mb-2">
                            <span className="text-secondary-text">Confidence Threshold</span>
                            <span className="text-text-color font-medium">{confidence}%</span>
                        </div>
                        <input
                            type="range"
                            value={confidence}
                            min={1}
                            max={100}
                            onChange={(e) => onConfidenceChange(Number(e.target.value))}
                            className="w-full h-1 bg-gray-500 rounded-full appearance-none cursor-pointer accent-text-color"
                        />
                    </div>
                </div>

                {/* Model Selection */}
                <div className="mt-4">
                    <div className="flex justify-between text-sm mb-2">
                        <span className="text-secondary-text">Model</span>
                        <span className="text-text-color font-medium">
                            {selectedModel?.short}
                        </span>
                    </div>
                    <select
                        value={model}
                        onChange={(e) => onModelChange(e.target.value)}
                        className="w-full bg-btn-bg text-text-color border border-btn-border rounded-lg p-1.5 text-xs"
                    >
                        {MODEL_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Advanced Settings */}
                <div className="mt-4">
                    <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        className="w-full flex items-center justify-between text-xs text-secondary-text hover:text-text-color transition-colors cursor-pointer py-2"
                    >
                        <span className="flex items-center gap-2">
                            Advanced Tracking Settings
                        </span>
                        <ChevronDown
                            className={`w-4 h-4 transition-transform ${showAdvanced ? "rotate-180" : ""
                                }`}
                        />
                    </button>

                    {showAdvanced && (
                        <div className="mt-3 space-y-4 pl-3 border-l-2 border-btn-border">
                            {/* Detection Quality */}
                            <div>
                                <div className="flex justify-between text-xs mb-1.5">
                                    <span className="text-secondary-text">Detection Quality</span>
                                    <span className="text-text-color font-medium">
                                        {trackerConfig.track_high_thresh.toFixed(2)}
                                    </span>
                                </div>
                                <input
                                    type="range"
                                    value={trackerConfig.track_high_thresh * 100}
                                    min={10}
                                    max={90}
                                    step={5}
                                    onChange={(e) =>
                                        handleTrackerSliderChange(
                                            "track_high_thresh",
                                            Number(e.target.value)
                                        )
                                    }
                                    className="w-full h-1 bg-gray-500 rounded-full appearance-none cursor-pointer accent-text-color"
                                />
                            </div>

                            {/* Recovery Sensitivity */}
                            <div>
                                <div className="flex justify-between text-xs mb-1.5">
                                    <span className="text-secondary-text">Recovery Sensitivity</span>
                                    <span className="text-text-color font-medium">
                                        {trackerConfig.track_low_thresh.toFixed(2)}
                                    </span>
                                </div>
                                <input
                                    type="range"
                                    value={trackerConfig.track_low_thresh * 100}
                                    min={1}
                                    max={50}
                                    onChange={(e) =>
                                        handleTrackerSliderChange(
                                            "track_low_thresh",
                                            Number(e.target.value)
                                        )
                                    }
                                    className="w-full h-1 bg-gray-500 rounded-full appearance-none cursor-pointer accent-text-color"
                                />
                            </div>

                            {/* Match Threshold */}
                            <div>
                                <div className="flex justify-between text-xs mb-1.5">
                                    <span className="text-secondary-text">Match Threshold</span>
                                    <span className="text-text-color font-medium">
                                        {trackerConfig.match_thresh.toFixed(2)}
                                    </span>
                                </div>
                                <input
                                    type="range"
                                    value={trackerConfig.match_thresh * 100}
                                    min={30}
                                    max={95}
                                    step={5}
                                    onChange={(e) =>
                                        handleTrackerSliderChange(
                                            "match_thresh",
                                            Number(e.target.value)
                                        )
                                    }
                                    className="w-full h-1 bg-gray-500 rounded-full appearance-none cursor-pointer accent-text-color"
                                />
                            </div>

                            {/* Track Memory */}
                            <div>
                                <div className="flex justify-between text-xs mb-1.5">
                                    <span className="text-secondary-text">Track Memory</span>
                                    <span className="text-text-color font-medium">
                                        {trackerConfig.track_buffer}
                                    </span>
                                </div>
                                <input
                                    type="range"
                                    value={trackerConfig.track_buffer}
                                    min={10}
                                    max={120}
                                    step={5}
                                    onChange={(e) =>
                                        handleTrackerSliderChange("track_buffer", Number(e.target.value))
                                    }
                                    className="w-full h-1 bg-gray-500 rounded-full appearance-none cursor-pointer accent-text-color"
                                />
                            </div>

                            <button
                                onClick={resetTrackerDefaults}
                                className="w-full text-xs text-secondary-text hover:text-text-color transition-colors py-1.5 cursor-pointer"
                            >
                                Reset to defaults
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Process Button */}
            <button
                onClick={onProcess}
                disabled={!canProcess || isProcessing}
                className={`w-full py-3 rounded-md text-sm font-medium transition-all ${canProcess && !isProcessing
                    ? "btn-primary"
                    : "bg-gray-500 text-gray-300 cursor-not-allowed"
                    }`}
            >
                {isProcessing ? "Processing..." : "Process"}
            </button>
        </section>
    );
}

// Add useState import
import { useState } from "react";
