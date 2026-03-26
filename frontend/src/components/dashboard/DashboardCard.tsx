"use client";

import { ReactNode } from "react";
import Tooltip from "./Tooltip";

interface DashboardCardProps {
    title: string;
    icon?: ReactNode;
    tooltip?: string;
    children: ReactNode;
    className?: string;
    contentClassName?: string;
}

export default function DashboardCard({
    title,
    icon,
    tooltip,
    children,
    className = "",
    contentClassName = ""
}: DashboardCardProps) {
    return (
        <div className={`bg-card-bg hover:bg-card-bg-hover rounded-md p-3 transition-colors ${className}`}>
            <div className="flex items-center gap-2 mb-2">
                {icon && <div className="text-secondary-text">{icon}</div>}
                <span className="text-xs font-medium text-text-color/90">{title}</span>
                {tooltip && (
                    <div className="ml-auto">
                        <Tooltip content={tooltip} />
                    </div>
                )}
            </div>
            <div className={`${contentClassName}`}>
                {children}
            </div>
        </div>
    );
}
