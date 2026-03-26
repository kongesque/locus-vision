import type { Job, ProgressResponse, SystemInfo, Zone, TrackerConfig } from "./types";

// API base URL - configure via environment variable
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * API client for communicating with the FastAPI backend
 */
class ApiClient {
    private baseUrl: string;

    constructor(baseUrl: string) {
        this.baseUrl = baseUrl;
    }

    private async request<T>(
        endpoint: string,
        options?: RequestInit
    ): Promise<T> {
        const url = `${this.baseUrl}${endpoint}`;
        const response = await fetch(url, {
            ...options,
            headers: {
                "Content-Type": "application/json",
                ...options?.headers,
            },
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    // ============ Jobs API ============

    /**
     * Upload a video file and create a new job
     */
    async uploadVideo(file: File): Promise<{ taskId: string }> {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(`${this.baseUrl}/api/jobs`, {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            throw new Error("Upload failed");
        }

        return response.json();
    }

    /**
     * Get a specific job by ID
     */
    async getJob(taskId: string): Promise<Job> {
        return this.request<Job>(`/api/jobs/${taskId}`);
    }

    /**
     * Get all completed jobs (history)
     */
    async getHistory(): Promise<Job[]> {
        return this.request<Job[]>("/api/jobs?status=completed");
    }

    /**
     * Delete a job
     */
    async deleteJob(taskId: string): Promise<void> {
        await this.request(`/api/jobs/${taskId}`, { method: "DELETE" });
    }

    /**
     * Clear all jobs and their associated files
     */
    async clearAllJobs(): Promise<{ success: boolean; deleted_count: number }> {
        return this.request("/api/jobs/all", { method: "DELETE" });
    }

    /**
     * Rename a job
     */
    async renameJob(taskId: string, name: string): Promise<void> {
        await this.request(`/api/jobs/${taskId}`, {
            method: "PATCH",
            body: JSON.stringify({ name }),
        });
    }

    // ============ Zones API ============

    /**
     * Update zones for a job
     */
    async updateZones(taskId: string, zones: Zone[]): Promise<void> {
        await this.request(`/api/jobs/${taskId}/zones`, {
            method: "PUT",
            body: JSON.stringify({ zones }),
        });
    }

    // ============ Processing API ============

    /**
     * Start processing a job
     */
    async processJob(
        taskId: string,
        options: {
            zones: Zone[];
            confidence: number;
            model: string;
            trackerConfig?: TrackerConfig;
        }
    ): Promise<{ success: boolean; redirect?: string }> {
        return this.request(`/api/jobs/${taskId}/process`, {
            method: "POST",
            body: JSON.stringify(options),
        });
    }

    /**
     * Get processing progress for a job
     */
    async getProgress(taskId: string): Promise<ProgressResponse> {
        return this.request<ProgressResponse>(`/api/jobs/${taskId}/progress`);
    }

    // ============ Export API ============

    /**
     * Get CSV export URL
     */
    getExportCsvUrl(taskId: string): string {
        return `${this.baseUrl}/api/jobs/${taskId}/export?format=csv`;
    }

    /**
     * Get JSON export URL
     */
    getExportJsonUrl(taskId: string): string {
        return `${this.baseUrl}/api/jobs/${taskId}/export?format=json`;
    }

    // ============ Live Stream API ============

    /**
     * Create a live stream job from RTSP URL
     */
    async createLiveStream(
        streamUrl: string,
        sourceType: "rtsp" | "webcam"
    ): Promise<{ taskId: string }> {
        return this.request("/api/camera", {
            method: "POST",
            body: JSON.stringify({ stream_url: streamUrl, source_type: sourceType }),
        });
    }

    /**
     * Test camera/RTSP connection
     */
    async testConnection(
        streamUrl: string
    ): Promise<{ success: boolean; width?: number; height?: number; error?: string }> {
        return this.request("/api/camera/test", {
            method: "POST",
            body: JSON.stringify({ stream_url: streamUrl }),
        });
    }

    /**
     * Stop a live stream
     */
    async stopLiveStream(taskId: string): Promise<void> {
        await this.request(`/api/live/${taskId}/stop`, { method: "POST" });
    }

    /**
     * Get live stream counts
     */
    async getLiveCounts(
        taskId: string
    ): Promise<{ counts: Record<string, number>; running: boolean }> {
        return this.request(`/api/live/${taskId}/counts`);
    }

    /**
     * Get WebSocket URL for live stream
     */
    getWebSocketUrl(taskId: string): string {
        const wsBase = this.baseUrl.replace("http", "ws");
        return `${wsBase}/ws/live/${taskId}`;
    }

    // ============ System API ============

    /**
     * Get system info (GPU status, version)
     */
    async getSystemInfo(): Promise<SystemInfo> {
        return this.request<SystemInfo>("/api/system-info");
    }

    // ============ Media URLs ============

    /**
     * Get URL for a media file (video, frame)
     */
    getMediaUrl(path: string): string {
        return `${this.baseUrl}/media/${path}`;
    }

    /**
     * Get output video URL
     */
    getOutputVideoUrl(taskId: string): string {
        return `${this.baseUrl}/media/outputs/output_${taskId}.mp4`;
    }
}

// Export singleton instance
export const api = new ApiClient(API_BASE_URL);
