"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Video, Wifi, AlertCircle, CheckCircle } from "lucide-react";
import { api } from "@/utils/api";

export default function CameraPage() {
    const router = useRouter();
    const [streamUrl, setStreamUrl] = useState("");
    const [sourceType, setSourceType] = useState<"rtsp" | "webcam">("rtsp");
    const [error, setError] = useState<string | null>(null);
    const [isConnecting, setIsConnecting] = useState(false);
    const [testResult, setTestResult] = useState<{
        success: boolean;
        width?: number;
        height?: number;
    } | null>(null);

    const handleTest = async () => {
        if (!streamUrl.trim()) {
            setError("Please enter a stream URL");
            return;
        }

        setIsConnecting(true);
        setError(null);
        setTestResult(null);

        try {
            const result = await api.testConnection(streamUrl);
            setTestResult(result);
            if (!result.success) {
                setError(result.error || "Connection failed");
            }
        } catch {
            setError("Failed to test connection");
        } finally {
            setIsConnecting(false);
        }
    };

    const handleConnect = async () => {
        if (!streamUrl.trim()) {
            setError("Please enter a stream URL");
            return;
        }

        setIsConnecting(true);
        setError(null);

        try {
            const result = await api.createLiveStream(streamUrl, sourceType);
            router.push(`/zone/${result.taskId}`);
        } catch (err: unknown) {
            const message = err instanceof Error ? err.message : "Connection failed";
            setError(message);
            setIsConnecting(false);
        }
    };

    return (
        <main className="flex-1 flex items-center justify-center p-4">
            <div className="w-full max-w-lg bg-primary-color border border-primary-border rounded-xl p-6">
                <div className="flex items-center gap-3 mb-6">
                    <Video className="w-8 h-8 text-dropzone-accent" />
                    <div>
                        <h1 className="text-xl font-semibold text-text-color">
                            Connect Camera
                        </h1>
                        <p className="text-sm text-secondary-text">
                            RTSP Stream or Webcam
                        </p>
                    </div>
                </div>

                {/* Source Type Selection */}
                <div className="flex gap-2 mb-4">
                    <button
                        onClick={() => {
                            setSourceType("rtsp");
                            setStreamUrl("");
                            setTestResult(null);
                        }}
                        className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${sourceType === "rtsp"
                            ? "bg-btn-hover border-text-color text-text-color border"
                            : "bg-btn-bg border-btn-border text-secondary-text border"
                            }`}
                    >
                        <Wifi className="w-4 h-4 inline mr-2" />
                        RTSP Stream
                    </button>
                    <button
                        onClick={() => {
                            setSourceType("webcam");
                            setStreamUrl("0");
                            setTestResult(null);
                        }}
                        className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${sourceType === "webcam"
                            ? "bg-btn-hover border-text-color text-text-color border"
                            : "bg-btn-bg border-btn-border text-secondary-text border"
                            }`}
                    >
                        <Video className="w-4 h-4 inline mr-2" />
                        Webcam
                    </button>
                </div>

                {/* Stream URL Input */}
                {sourceType === "rtsp" && (
                    <div className="mb-4">
                        <label className="block text-sm text-secondary-text mb-2">
                            Stream URL
                        </label>
                        <input
                            type="text"
                            value={streamUrl}
                            onChange={(e) => {
                                setStreamUrl(e.target.value);
                                setTestResult(null);
                                setError(null);
                            }}
                            placeholder="rtsp://username:password@ip:port/path"
                            className="w-full bg-btn-bg text-text-color border border-btn-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-dropzone-accent"
                        />
                    </div>
                )}

                {/* Webcam Selection */}
                {sourceType === "webcam" && (
                    <div className="mb-4">
                        <label className="block text-sm text-secondary-text mb-2">
                            Camera Index
                        </label>
                        <select
                            value={streamUrl}
                            onChange={(e) => setStreamUrl(e.target.value)}
                            className="w-full bg-btn-bg text-text-color border border-btn-border rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-dropzone-accent"
                        >
                            <option value="0">Camera 0 (Default)</option>
                            <option value="1">Camera 1</option>
                            <option value="2">Camera 2</option>
                        </select>
                    </div>
                )}

                {/* Error Message */}
                {error && (
                    <div className="flex items-center gap-2 p-3 mb-4 bg-delete-text/10 border border-delete-text/30 rounded-lg text-sm text-delete-text">
                        <AlertCircle className="w-4 h-4 flex-shrink-0" />
                        {error}
                    </div>
                )}

                {/* Test Result */}
                {testResult?.success && (
                    <div className="flex items-center gap-2 p-3 mb-4 bg-green-500/10 border border-green-500/30 rounded-lg text-sm text-green-400">
                        <CheckCircle className="w-4 h-4 flex-shrink-0" />
                        Connected! Resolution: {testResult.width}×{testResult.height}
                    </div>
                )}

                {/* Buttons */}
                <div className="flex gap-2">
                    <button
                        onClick={handleTest}
                        disabled={isConnecting || !streamUrl.trim()}
                        className="flex-1 btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isConnecting ? "Testing..." : "Test Connection"}
                    </button>
                    <button
                        onClick={handleConnect}
                        disabled={isConnecting || !streamUrl.trim()}
                        className="flex-1 btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isConnecting ? "Connecting..." : "Connect"}
                    </button>
                </div>

                {/* Help Text */}
                <div className="mt-6 text-xs text-secondary-text">
                    <p className="font-medium mb-2">RTSP URL Examples:</p>
                    <ul className="space-y-1 list-disc list-inside">
                        <li>rtsp://admin:password@192.168.1.100:554/stream1</li>
                        <li>rtsp://192.168.1.100:8554/live</li>
                        <li>rtsp://user:pass@camera.local/h264</li>
                    </ul>
                </div>
            </div>
        </main>
    );
}
