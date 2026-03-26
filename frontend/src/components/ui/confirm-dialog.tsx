"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

interface ConfirmDialogProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    title: string;
    description: string;
    confirmText?: string;
    cancelText?: string;
    variant?: "default" | "destructive";
    isLoading?: boolean;
}

export function ConfirmDialog({
    isOpen,
    onClose,
    onConfirm,
    title,
    description,
    confirmText = "Continue",
    cancelText = "Cancel",
    variant = "default",
    isLoading = false,
}: ConfirmDialogProps) {
    const [mounted, setMounted] = useState(false);
    const [isVisible, setIsVisible] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    useEffect(() => {
        if (isOpen) {
            setIsVisible(true);
            document.body.style.overflow = "hidden";
        } else {
            const timer = setTimeout(() => setIsVisible(false), 200);
            document.body.style.overflow = "unset";
            return () => clearTimeout(timer);
        }
        return () => {
            document.body.style.overflow = "unset";
        };
    }, [isOpen]);

    if (!mounted) return null;
    if (!isVisible && !isOpen) return null;

    return createPortal(
        <div className="fixed inset-0 z-[100] flex items-center justify-center font-sans">
            {/* Backdrop */}
            <div
                className={`fixed inset-0 bg-black/80 transition-opacity duration-200 ${isOpen ? "opacity-100" : "opacity-0"
                    }`}
                onClick={isLoading ? undefined : onClose}
            />

            {/* Dialog Content */}
            <div
                className={`fixed z-[101] w-full max-w-md scale-100 gap-4 border border-[var(--color-primary-border)] bg-[var(--color-bg-1)] p-6 shadow-lg transition-all duration-200 sm:rounded-lg md:w-full ${isOpen
                    ? "opacity-100 translate-y-0 scale-100"
                    : "opacity-0 translate-y-4 scale-95"
                    }`}
            >
                <div className="flex flex-col space-y-2 text-center sm:text-left">
                    <h2 className="text-lg font-semibold leading-none tracking-tight text-[var(--color-text-color)]">
                        {title}
                    </h2>
                    <p className="text-sm text-[var(--color-secondary-text)]">
                        {description}
                    </p>
                </div>

                <div className="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-6 gap-2 sm:gap-0">
                    <button
                        onClick={onClose}
                        disabled={isLoading}
                        className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary-border)] disabled:pointer-events-none disabled:opacity-50 border border-[var(--color-btn-border)] bg-[var(--color-bg-1)] hover:bg-[var(--color-btn-hover)] text-[var(--color-text-color)] h-10 px-4 py-2"
                    >
                        {cancelText}
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={isLoading}
                        className={`inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary-border)] disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 text-white shadow hover:opacity-90 ${variant === "destructive"
                            ? "bg-red-600 hover:bg-red-700"
                            : "bg-[var(--color-text-color)] text-[var(--color-bg-1)]"
                            }`}
                    >
                        {isLoading ? "Processing..." : confirmText}
                    </button>
                </div>

                <button
                    onClick={onClose}
                    disabled={isLoading}
                    className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-[var(--color-bg-1)] transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary-border)] focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-[var(--color-btn-hover)] data-[state=open]:text-[var(--color-text-color)]"
                >
                    <X className="h-4 w-4 text-[var(--color-text-color)]" />
                    <span className="sr-only">Close</span>
                </button>
            </div>
        </div>,
        document.body
    );
}
