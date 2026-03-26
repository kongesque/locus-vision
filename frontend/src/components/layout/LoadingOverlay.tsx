"use client";

interface LoadingOverlayProps {
    message?: string;
    description?: string;
    progress?: number;
}

export function LoadingOverlay({
    message = "Processing...",
    description = "The process may take a moment, please keep this window open.",
    progress,
}: LoadingOverlayProps) {
    return (
        <div className="loading-overlay">
            {/* Spinner */}
            <div className="w-12 h-12 border-4 border-gray-500 border-t-text-color rounded-full animate-spin mb-4" />

            {/* Message */}
            <p className="text-xl font-semibold text-text-color">{message}</p>

            {/* Description */}
            <span className="text-sm text-gray-300 mt-2 text-center max-w-sm">
                {description}
            </span>

            {/* Progress bar (optional) */}
            {progress !== undefined && (
                <div className="w-64 h-2 bg-gray-500 rounded-full mt-4 overflow-hidden">
                    <div
                        className="h-full bg-dropzone-accent rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            )}
            {progress !== undefined && (
                <span className="text-xs text-muted-foreground mt-2">{progress}%</span>
            )}
        </div>
    );
}
