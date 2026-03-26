"use client";

import { useCallback, useState, useEffect } from "react";
import { useDropzone } from "react-dropzone";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { Upload, Video, PanelLeft } from "lucide-react";
import { api } from "@/utils/api";
import { LoadingOverlay, Sidebar } from "@/components/layout";

export default function HomePage() {
  const router = useRouter();
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load saved sidebar state after mount to prevent hydration mismatch
  useEffect(() => {
    setTimeout(() => {
      setMounted(true);
      const saved = localStorage.getItem("sidebarOpen");
      if (saved !== null) {
        setSidebarOpen(saved === "true");
      }
    }, 0);
  }, []);

  const toggleSidebar = () => {
    const newState = !sidebarOpen;
    setSidebarOpen(newState);
    localStorage.setItem("sidebarOpen", String(newState));
  };

  // Fetch job history
  const { data: jobs = [], refetch } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.getHistory(),
  });

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      if (acceptedFiles.length === 0) return;

      const file = acceptedFiles[0];
      setIsUploading(true);
      setUploadError(null);

      try {
        const result = await api.uploadVideo(file);
        router.push(`/zone/${result.taskId}`);
      } catch (error) {
        console.error("Upload failed:", error);
        setUploadError("Upload failed. Please try again.");
        setIsUploading(false);
      }
    },
    [router]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "video/*": [".mp4", ".webm", ".mov", ".avi"],
    },
    multiple: false,
  });

  const handleJobDeleted = () => {
    refetch();
  };

  const handleJobRenamed = () => {
    refetch();
  };

  if (isUploading) {
    return (
      <LoadingOverlay
        message="Uploading files..."
        description="The process may take a moment, please keep this window open."
      />
    );
  }

  return (
    <>
      {/* Sidebar - only show after mount to prevent hydration flicker */}
      {mounted && (
        <Sidebar
          jobs={jobs}
          isOpen={sidebarOpen}
          onJobDeleted={handleJobDeleted}
          onJobRenamed={handleJobRenamed}
        />
      )}

      {/* Main Content */}
      <main className="relative flex-1 flex items-center justify-center flex-col text-center mx-2 mt-0 mb-2 overflow-hidden bg-primary-color border border-primary-border rounded-md">
        {/* Toggle Sidebar Button - Inside Main Content */}
        <button
          onClick={toggleSidebar}
          className="absolute top-4 left-4 p-1.5 rounded-md hover:bg-sidebar-accent transition-colors cursor-pointer"
          title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
        >
          <PanelLeft className="w-5 h-5 opacity-80 text-text-color" />
        </button>

        {/* Title */}
        <div className="mb-4">
          <h1 className="text-3xl md:text-5xl font-bold text-sidebar-foreground tracking-tight leading-tight">
            What do you want to count?
          </h1>
        </div>

        {/* Upload Area */}
        <div className="flex flex-col items-center justify-center px-4">
          <div
            {...getRootProps()}
            className={`w-full max-w-6xl py-6 px-16 md:px-64 text-center rounded-xl cursor-pointer transition-all duration-200 bg-dropzone-hover-bg border-[2px] border-dashed ${isDragActive
              ? "border-dropzone-accent bg-sidebar-item-hover"
              : "border-dropzone-border hover:border-dropzone-accent"
              } group`}
          >
            <input {...getInputProps()} />

            <div className="flex flex-col items-center gap-4 md:gap-5 pointer-events-none">
              {/* Icon and text */}
              <div className="flex items-center gap-3 transition-colors">
                <Upload
                  className={`w-8 h-8 ${isDragActive ? "text-dropzone-accent" : "text-dropzone-accent"
                    }`}
                />
                <span className="font-bold text-xl text-text-color">
                  {isDragActive ? "Drop it here!" : "Choose Files"}
                </span>
              </div>

              <p className="text-sm text-secondary-text">or drop it here</p>

              {/* Supported formats */}
              <div className="flex items-center gap-3">
                <span className="px-3 py-1 text-xs text-secondary-text border border-secondary-text rounded-full">
                  .MP4
                </span>
                <span className="px-3 py-1 text-xs text-secondary-text border border-secondary-text rounded-full">
                  .WebM
                </span>
              </div>
            </div>
          </div>

          {/* Error message */}
          {uploadError && (
            <p className="mt-4 text-sm text-delete-text">{uploadError}</p>
          )}

          {/* Connect Camera Button */}
          <Link
            href="/camera"
            className="flex items-center gap-2 mt-4 px-4 py-2 text-sm text-secondary-text border border-primary-border rounded-full hover:text-text-color hover:border-text-color hover:bg-btn-hover transition-all cursor-pointer no-underline"
          >
            <Video className="w-4 h-4" />
            <span>Connect Live Camera (RTSP / Webcam)</span>
          </Link>
        </div>
      </main>
    </>
  );
}
