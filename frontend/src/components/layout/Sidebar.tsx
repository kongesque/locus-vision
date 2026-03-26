"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { MoreHorizontal, Trash2, Edit2 } from "lucide-react";
import type { Job } from "@/utils/types";
import { api } from "@/utils/api";

interface SidebarProps {
    jobs: Job[];
    activeTaskId?: string;
    isOpen: boolean;
    onJobDeleted?: (taskId: string) => void;
    onJobRenamed?: (taskId: string, newName: string) => void;
}

export function Sidebar({
    jobs,
    activeTaskId,
    isOpen,
    onJobDeleted,
    onJobRenamed,
}: SidebarProps) {
    const [menuOpen, setMenuOpen] = useState<string | null>(null);
    const [editingId, setEditingId] = useState<string | null>(null);
    const [editName, setEditName] = useState("");
    const [enableTransition, setEnableTransition] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    // Enable transition only after initial render to prevent flash
    useEffect(() => {
        const timer = setTimeout(() => setEnableTransition(true), 100);
        return () => clearTimeout(timer);
    }, []);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setMenuOpen(null);
            }
        };

        if (menuOpen) {
            document.addEventListener("mousedown", handleClickOutside);
        }

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [menuOpen]);

    const handleMenuClick = (e: React.MouseEvent, jobId: string) => {
        e.preventDefault();
        e.stopPropagation();
        setMenuOpen(menuOpen === jobId ? null : jobId);
    };

    const handleRename = (jobId: string, currentName: string) => {
        setEditingId(jobId);
        setEditName(currentName || "Untitled");
        setMenuOpen(null);
    };

    const handleSaveRename = async (jobId: string) => {
        if (editName.trim()) {
            try {
                await api.renameJob(jobId, editName.trim());
                onJobRenamed?.(jobId, editName.trim());
            } catch (error) {
                console.error("Failed to rename job:", error);
            }
        }
        setEditingId(null);
    };

    const handleDelete = async (jobId: string) => {
        try {
            await api.deleteJob(jobId);
            onJobDeleted?.(jobId);
        } catch (error) {
            console.error("Failed to delete job:", error);
        }
        setMenuOpen(null);
    };

    return (
        <aside
            className={`h-full bg-background flex-col overflow-hidden hidden lg:flex ${enableTransition ? "transition-all duration-300 ease-in-out" : ""
                } ${isOpen ? "w-60" : "w-0"}`}
        >
            <nav
                className={`flex-1 p-2 space-y-1 overflow-y-auto overflow-x-hidden w-60 ${enableTransition ? "transition-opacity duration-200" : ""
                    } ${isOpen ? "opacity-100" : "opacity-0"}`}
            >
                {/* Section Header */}
                <div className="px-2 py-2">
                    <span className="text-sm font-medium text-sidebar-foreground whitespace-nowrap">
                        History
                    </span>
                </div>

                {/* Navigation Items */}
                {jobs.length === 0 ? (
                    <div className="px-2 py-2 text-xs text-secondary-text italic">
                        No history yet
                    </div>
                ) : (
                    jobs.map((job) => (
                        <div
                            key={job.id}
                            className={`group relative flex items-center rounded-md hover:bg-sidebar-item-hover pr-2 ${activeTaskId === job.id
                                    ? "bg-sidebar-accent text-sidebar-foreground"
                                    : ""
                                }`}
                        >
                            {editingId === job.id ? (
                                <input
                                    type="text"
                                    value={editName}
                                    onChange={(e) => setEditName(e.target.value)}
                                    onBlur={() => handleSaveRename(job.id)}
                                    onKeyDown={(e) => {
                                        if (e.key === "Enter") handleSaveRename(job.id);
                                        if (e.key === "Escape") setEditingId(null);
                                    }}
                                    className="flex-1 px-2 py-2 text-sm text-sidebar-foreground bg-transparent border-b border-gray-600 outline-none focus:border-blue-500"
                                    autoFocus
                                />
                            ) : (
                                <>
                                    <Link
                                        href={`/result/${job.id}`}
                                        id={`title-${job.id}`}
                                        className={`flex-1 block px-2 py-2 text-sm whitespace-nowrap overflow-hidden text-ellipsis no-underline ${activeTaskId === job.id
                                                ? "font-medium text-sidebar-foreground"
                                                : "text-muted-foreground hover:text-sidebar-foreground"
                                            }`}
                                    >
                                        {job.name || job.filename || "Untitled"}
                                    </Link>

                                    {/* 3-dot Menu Trigger */}
                                    <button
                                        id={`menu-btn-${job.id}`}
                                        onClick={(e) => handleMenuClick(e, job.id)}
                                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-sidebar-menu-hover text-muted-foreground transition-opacity"
                                    >
                                        <MoreHorizontal className="w-4 h-4 opacity-80" />
                                    </button>
                                </>
                            )}

                            {/* Dropdown Menu */}
                            {menuOpen === job.id && (
                                <div
                                    ref={menuRef}
                                    className="absolute right-0 top-full z-[9999] w-32 bg-btn-bg border border-btn-border rounded shadow-lg flex-col py-1"
                                >
                                    <button
                                        onClick={() =>
                                            handleRename(job.id, job.name || job.filename)
                                        }
                                        className="w-full text-left px-3 py-1.5 text-xs text-text-color hover:bg-btn-hover flex items-center gap-2"
                                    >
                                        <Edit2 className="w-3 h-3" />
                                        Rename
                                    </button>
                                    <button
                                        onClick={() => handleDelete(job.id)}
                                        className="w-full text-left px-3 py-1.5 text-xs text-delete-text hover:bg-delete-text/10 flex items-center gap-2"
                                    >
                                        <Trash2 className="w-3 h-3" />
                                        Delete
                                    </button>
                                </div>
                            )}
                        </div>
                    ))
                )}
            </nav>
        </aside>
    );
}
