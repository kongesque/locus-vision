"use client";

import { Info } from "lucide-react";
import { ReactNode } from "react";

interface TooltipProps {
    content: string | ReactNode;
    children?: ReactNode;
    className?: string;
}

export default function Tooltip({ content, children, className = "" }: TooltipProps) {
    return (
        <div className={`group/tooltip relative inline-flex items-center ${className}`}>
            {children || <Info className="w-3.5 h-3.5 text-secondary-text hover:text-text-color transition-colors cursor-help opacity-70 hover:opacity-100" />}

            <div className="absolute right-full top-1/2 -translate-y-1/2 mr-3 px-3 py-2 bg-btn-bg border border-btn-border rounded-lg shadow-xl opacity-0 invisible group-hover/tooltip:opacity-100 group-hover/tooltip:visible transition-all duration-200 z-50 w-max max-w-[200px] text-xs leading-relaxed text-text-color pointer-events-none">
                {content}
                {/* Arrow pointing right (towards the icon) */}
                <div className="absolute top-1/2 -right-1 -translate-y-1/2 w-2 h-2 bg-btn-bg border-t border-r border-btn-border rotate-45" />
            </div>
        </div>
    );
}
