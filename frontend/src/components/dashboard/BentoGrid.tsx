"use client";

import { ReactNode } from "react";

export function BentoGrid({
    className,
    children,
}: {
    className?: string;
    children: ReactNode;
}) {
    return (
        <div
            className={`grid w-full h-full gap-4 ${className}`}
        >
            {children}
        </div>
    );
}

export function BentoCard({
    className,
    children,
    title,
    icon,
    noScroll,
    noSpacer,
    darkHeader,
    headerAction,
}: {
    className?: string;
    children: ReactNode;
    title?: string;
    icon?: ReactNode;
    noScroll?: boolean;
    noSpacer?: boolean;
    darkHeader?: boolean;
    headerAction?: ReactNode;
}) {
    return (
        <div
            className={`group relative flex flex-col overflow-hidden rounded-xl
      border border-primary-border bg-btn-bg/50 backdrop-blur-md shadow-2xl
      transition-all duration-300 hover:border-gray-500/30
      ${className}`}
        >
            {/* Header - Absolute positioned, pointer-events-none to allow clicking through to spacer if needed, 
                but we usually want the header to be visual. z-30 to stay on top of scrollable content. */
            }
            {(title || icon || headerAction) && (
                <div className={`absolute top-0 left-0 w-full px-2 py-2 z-30 flex items-center gap-2 bg-gradient-to-b to-transparent pointer-events-none ${darkHeader ? 'from-black/60' : 'from-bg-color/90'}`}>
                    {icon && <span className={`${darkHeader ? 'text-white/70' : 'text-text-color/70'}`}>{icon}</span>}
                    {title && <h3 className={`font-semibold text-xs tracking-wider uppercase ${darkHeader ? 'text-white/90' : 'text-text-color/90'}`}>{title}</h3>}

                    {headerAction && (
                        <div className="ml-auto pointer-events-auto">
                            {headerAction}
                        </div>
                    )}
                </div>
            )}

            {/* Content Container - z-20 to sit above hover/decor effects */}
            <div className="relative z-20 flex-1 w-full h-full overflow-hidden flex flex-col">
                <div className={`flex-1 w-full h-full ${noScroll ? 'overflow-hidden' : 'overflow-y-auto'}`}>
                    {/* Spacer to prevent content from starting under the header (unless disabled) */}
                    {(!noSpacer && (title || icon)) && <div className="h-10 w-full shrink-0" />}
                    {children}
                </div>
            </div>

            {/* Subtle decorative gradient - z-10 (behind content) */}
            <div className="pointer-events-none absolute inset-0 transform-gpu transition-all duration-300 group-hover:bg-text-color/[0.01] z-10" />
        </div>
    );
}
