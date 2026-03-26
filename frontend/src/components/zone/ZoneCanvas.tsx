"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { Zone, Point } from "@/utils/types";

interface ZoneCanvasProps {
    frameUrl: string;
    zones: Zone[];
    activeZoneId: string | null;
    maxPoints: number;
    onZonesChange: (zones: Zone[]) => void;
    onPointAdded: (zoneId: string, point: Point) => void;
    onFrameLoaded: (width: number, height: number) => void;
    onZoneSelect: (zoneId: string) => void;
    onAutoCreateZone: (firstPoint: Point) => void;
}

function getColorFromClassId(classId: number): string {
    const hue = ((classId * 137.508) % 360);
    return `hsl(${hue}, 85%, 55%)`;
}

export function ZoneCanvas({
    frameUrl,
    zones,
    activeZoneId,
    maxPoints,
    onZonesChange,
    onPointAdded,
    onFrameLoaded,
    onZoneSelect,
    onAutoCreateZone,
}: ZoneCanvasProps) {
    const canvasRef = useRef<HTMLCanvasElement>(null);
    const imageRef = useRef<HTMLImageElement | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const [imageLoaded, setImageLoaded] = useState(false);
    const [scale, setScale] = useState(1);
    const [mousePos, setMousePos] = useState<{ x: number; y: number } | null>(null);

    // Dragging state
    const [draggedPoint, setDraggedPoint] = useState<{ zoneId: string; index: number } | null>(null);
    const [draggedZone, setDraggedZone] = useState<{ zoneId: string; offset: Point } | null>(null);
    const [hoveredPoint, setHoveredPoint] = useState<{ zoneId: string; index: number } | null>(null);
    const [hoveredZoneId, setHoveredZoneId] = useState<string | null>(null);

    // Load the frame image
    useEffect(() => {
        const img = new Image();
        img.crossOrigin = "anonymous";
        img.onload = () => {
            imageRef.current = img;
            setImageLoaded(true);
            onFrameLoaded(img.width, img.height);
        };
        img.src = frameUrl;
    }, [frameUrl, onFrameLoaded]);

    // Calculate scale and offset to fit canvas in container
    const updateCanvasSize = useCallback(() => {
        const canvas = canvasRef.current;
        const container = containerRef.current;
        const img = imageRef.current;

        if (!canvas || !container || !img) return;

        const containerRect = container.getBoundingClientRect();
        const containerWidth = containerRect.width - 32;
        const containerHeight = containerRect.height - 32;

        const scaleX = containerWidth / img.width;
        const scaleY = containerHeight / img.height;
        const newScale = Math.min(scaleX, scaleY);

        canvas.width = img.width * newScale;
        canvas.height = img.height * newScale;

        setScale(newScale);
    }, []);

    useEffect(() => {
        if (!imageLoaded || !containerRef.current) return;

        // Initial update
        updateCanvasSize();

        // Use ResizeObserver for robust responsiveness
        const resizeObserver = new ResizeObserver(() => {
            updateCanvasSize();
        });

        resizeObserver.observe(containerRef.current);

        return () => {
            resizeObserver.disconnect();
        };
    }, [imageLoaded, updateCanvasSize]);

    // Helpers for hit detection
    const getPointAt = useCallback((x: number, y: number): { zoneId: string; index: number } | null => {
        const threshold = 10 / scale; // 10 pixels hit area
        for (const zone of zones) {
            for (let i = 0; i < zone.points.length; i++) {
                const p = zone.points[i];
                const dist = Math.sqrt((p.x - x) ** 2 + (p.y - y) ** 2);
                if (dist <= threshold) return { zoneId: zone.id, index: i };
            }
        }
        return null;
    }, [zones, scale]);

    const isPointInPolygon = (p: Point, points: Point[]): boolean => {
        let inside = false;
        for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
            const xi = points[i].x, yi = points[i].y;
            const xj = points[j].x, yj = points[j].y;
            const intersect = ((yi > p.y) !== (yj > p.y))
                && (p.x < (xj - xi) * (p.y - yi) / (yj - yi) + xi);
            if (intersect) inside = !inside;
        }
        return inside;
    };

    const getZoneAt = useCallback((x: number, y: number): string | null => {
        // Search in reverse to hit the topmost zone first
        for (let i = zones.length - 1; i >= 0; i--) {
            const zone = zones[i];
            if (zone.points.length >= 3 && isPointInPolygon({ x, y }, zone.points)) {
                return zone.id;
            }
        }
        return null;
    }, [zones]);

    // Draw canvas content with premium UX
    const drawCanvas = useCallback(() => {
        const canvas = canvasRef.current;
        const ctx = canvas?.getContext("2d");
        const img = imageRef.current;

        if (!canvas || !ctx || !img || !imageLoaded) return;

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw background image
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

        // Helper to draw vertices
        const drawVertex = (x: number, y: number, color: string, isActive: boolean, isHovered: boolean, isStart: boolean = false) => {
            const baseRadius = isActive ? 5 : 4;
            const radius = isHovered ? baseRadius + 2 : baseRadius;

            ctx.beginPath();
            ctx.arc(x, y, radius, 0, Math.PI * 2);

            // White fill, colored border (Premium look)
            ctx.fillStyle = "#ffffff";
            ctx.fill();

            ctx.lineWidth = 2;
            ctx.strokeStyle = color;
            ctx.stroke();

            // Additional ring for start point (Magnetic target) or hovered
            if (isStart || isHovered) {
                ctx.beginPath();
                ctx.arc(x, y, radius + 3, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(255, 255, 255, 0.5)`;
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        };

        // Draw all zones
        zones.forEach((zone) => {
            if (zone.points.length === 0) return;

            const isActive = zone.id === activeZoneId;
            const isHovered = zone.id === hoveredZoneId;
            const color = getColorFromClassId(zone.classIds[0]);

            // Scale points
            const scaledPoints = zone.points.map((p) => ({
                x: p.x * scale,
                y: p.y * scale,
            }));

            // --- DOUBLE STROKE SYSTEM (Visibility on any background) ---

            ctx.lineJoin = "round";
            ctx.lineCap = "round";

            // 1. Draw Fill (Active/Hovered only)
            if (zone.points.length >= 3) {
                const alpha = (isActive || isHovered) ? 0.25 : 0.15;
                ctx.fillStyle = color.replace(")", `, ${alpha})`).replace("hsl", "hsla");
                ctx.beginPath();
                ctx.moveTo(scaledPoints[0].x, scaledPoints[0].y);
                for (let i = 1; i < scaledPoints.length; i++) {
                    ctx.lineTo(scaledPoints[i].x, scaledPoints[i].y);
                }
                // Close polygon logic for fill
                if (zone.points.length >= 3 && !isActive) {
                    ctx.closePath();
                }
                ctx.fill();
            }

            // 2. Outer Contrast Stroke (White/Black glow)
            // Only draw if we have points and lines
            if (scaledPoints.length > 1) {
                ctx.beginPath();
                ctx.moveTo(scaledPoints[0].x, scaledPoints[0].y);
                for (let i = 1; i < scaledPoints.length; i++) {
                    ctx.lineTo(scaledPoints[i].x, scaledPoints[i].y);
                }
                if (zone.points.length >= 3 && !isActive) {
                    ctx.closePath();
                }

                ctx.lineWidth = isActive ? 5 : 3;
                ctx.strokeStyle = "rgba(0,0,0,0.5)"; // Dark outer glow for depth
                ctx.stroke();

                // 3. Inner Color Stroke
                ctx.lineWidth = isActive ? 3 : 2;
                ctx.strokeStyle = color;
                ctx.stroke();
            }

            // Draw Vertices
            scaledPoints.forEach((point, idx) => {
                const isPointHovered = hoveredPoint?.zoneId === zone.id && hoveredPoint?.index === idx;
                const isStartPoint = idx === 0 && isActive && zone.points.length >= 3; // Highlight start point if closing is possible

                drawVertex(point.x, point.y, color, isActive, isPointHovered, isStartPoint);

                // Show numbers only on hover or for start/end
                if (isPointHovered || idx === 0 || idx === scaledPoints.length - 1) {
                    // Small number pill
                    ctx.font = "10px sans-serif";
                    ctx.fillStyle = "rgba(0,0,0,0.7)";
                    const text = String(idx + 1);
                    const metrics = ctx.measureText(text);
                    const pillWidth = metrics.width + 8;

                    // Draw number pill offset from point
                    const pillX = point.x + 12;
                    const pillY = point.y - 12;

                    ctx.beginPath();
                    ctx.roundRect(pillX, pillY, pillWidth, 14, 4);
                    ctx.fill();

                    ctx.fillStyle = "#fff";
                    ctx.textAlign = "left";
                    ctx.textBaseline = "top";
                    ctx.fillText(text, pillX + 4, pillY + 2);
                }
            });

            // Draw Zone Label (Top-Left of first point)
            if (scaledPoints.length > 0) {
                const labelPoint = scaledPoints[0];
                ctx.font = "bold 13px sans-serif";
                const labelText = zone.label;
                const metrics = ctx.measureText(labelText);

                ctx.fillStyle = color;
                // Background for label
                ctx.fillRect(labelPoint.x, labelPoint.y - 24, metrics.width + 12, 20);

                // High contrast text based on color brightness? For now white.
                ctx.fillStyle = "#fff";
                ctx.textAlign = "left";
                ctx.textBaseline = "middle";
                ctx.fillText(labelText, labelPoint.x + 6, labelPoint.y - 14);
            }
        });

        // --- GHOST LINE & MAGNETIC SNAP (Active Drawing State) ---
        const activeZone = zones.find((z) => z.id === activeZoneId);
        if (activeZone && activeZone.points.length > 0 && activeZone.points.length < maxPoints && mousePos && !draggedPoint && !draggedZone) {
            const color = getColorFromClassId(activeZone.classIds[0]);
            const lastPoint = activeZone.points[activeZone.points.length - 1];
            const startPoint = activeZone.points[0];

            const scaledLast = { x: lastPoint.x * scale, y: lastPoint.y * scale };
            const scaledMouse = { x: mousePos.x * scale, y: mousePos.y * scale };
            let targetPoint = scaledMouse;

            // MAGNETIC SNAP: Check if near start point to close
            if (activeZone.points.length >= 3) {
                const scaledStart = { x: startPoint.x * scale, y: startPoint.y * scale };
                const distToStart = Math.sqrt((scaledMouse.x - scaledStart.x) ** 2 + (scaledMouse.y - scaledStart.y) ** 2);
                if (distToStart < 20) { // 20px snap radius (visual)
                    targetPoint = scaledStart;
                    // Draw Snap Indicator (Target)
                    ctx.beginPath();
                    ctx.arc(scaledStart.x, scaledStart.y, 8, 0, Math.PI * 2);
                    ctx.strokeStyle = "#fff";
                    ctx.lineWidth = 2;
                    ctx.setLineDash([2, 2]);
                    ctx.stroke();
                    ctx.setLineDash([]);
                }
            }

            // Draw "Ghost Line" (Dashed)
            ctx.beginPath();
            ctx.moveTo(scaledLast.x, scaledLast.y);
            ctx.lineTo(targetPoint.x, targetPoint.y);

            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]); // Dashed line
            ctx.stroke();
            ctx.setLineDash([]); // Reset

            // Draw cursor follower vertex (smaller)
            ctx.beginPath();
            ctx.arc(targetPoint.x, targetPoint.y, 6, 0, Math.PI * 2);
            ctx.fillStyle = "#ffffff";
            ctx.fill();
            ctx.lineWidth = 2;
            ctx.strokeStyle = color;
            ctx.stroke();
        }
    }, [zones, activeZoneId, scale, imageLoaded, mousePos, maxPoints, hoveredPoint, draggedPoint, hoveredZoneId, draggedZone]);

    // Redraw on changes
    useEffect(() => {
        drawCanvas();
    }, [drawCanvas]);

    // Handle canvas mouse down
    const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left) / scale;
        const y = (e.clientY - rect.top) / scale;

        // 1. Check if clicking on a point (drag point)
        let pointHit = getPointAt(x, y);

        // SPECIAL: Magnetic Snap for closing active polygon
        // If we missed a precise point hit, but are within "Snap Radius" (20px) of start point -> Close it
        if (!pointHit && activeZoneId) {
            const activeZone = zones.find(z => z.id === activeZoneId);
            if (activeZone && activeZone.points.length >= 3) {
                const startPoint = activeZone.points[0];
                const dist = Math.sqrt((startPoint.x - x) ** 2 + (startPoint.y - y) ** 2);
                if (dist <= 20 / scale) {
                    pointHit = { zoneId: activeZoneId, index: 0 };
                }
            }
        }

        if (pointHit) {
            // Check if clicking on first point of active zone with 3+ points (close polygon)
            if (activeZoneId && pointHit.zoneId === activeZoneId && pointHit.index === 0) {
                const activeZone = zones.find(z => z.id === activeZoneId);
                if (activeZone && activeZone.points.length >= 3) {
                    // Close the polygon by moving to a new zone (deselect current)
                    onAutoCreateZone({ x: -1, y: -1 }); // Signal to create empty new zone
                    return;
                }
            }
            setDraggedPoint(pointHit);
            return;
        }

        // 2. Check if clicking inside a zone
        const zoneId = getZoneAt(x, y);
        if (zoneId) {
            // If clicking on a different zone, SELECT it
            if (activeZoneId !== zoneId) {
                onZoneSelect(zoneId);
                return;
            }
            // If clicking inside the ACTIVE zone, add a point there (not drag)
            // This allows creating complex concave polygons
        }

        // 3. Clicking on empty area
        const newPoint = { x: Math.round(x), y: Math.round(y) };

        if (activeZoneId) {
            const activeZone = zones.find((z) => z.id === activeZoneId);
            if (activeZone && activeZone.points.length < maxPoints) {
                // Add point to active zone
                onPointAdded(activeZoneId, newPoint);
            } else {
                // Active zone is complete, auto-create new zone
                onAutoCreateZone(newPoint);
            }
        } else {
            // No active zone, auto-create new zone with first point
            onAutoCreateZone(newPoint);
        }
    };

    // Handle double-click to close polygon (deselect current zone)
    const handleDoubleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
        e.preventDefault();
        if (!activeZoneId) return;

        const activeZone = zones.find(z => z.id === activeZoneId);
        if (activeZone && activeZone.points.length >= 2) {
            // Zone has enough points, close it by auto-creating a new zone
            onAutoCreateZone({ x: -1, y: -1 }); // Signal to create empty new zone
        }
    };

    // Handle mouse move
    const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left) / scale;
        const y = (e.clientY - rect.top) / scale;

        setMousePos({ x, y });

        if (draggedPoint) {
            const updatedZones = zones.map(z => {
                if (z.id === draggedPoint.zoneId) {
                    const newPoints = [...z.points];
                    newPoints[draggedPoint.index] = { x: Math.round(x), y: Math.round(y) };
                    return { ...z, points: newPoints };
                }
                return z;
            });
            onZonesChange(updatedZones);
        } else if (draggedZone) {
            const dx = x - draggedZone.offset.x;
            const dy = y - draggedZone.offset.y;

            const updatedZones = zones.map(z => {
                if (z.id === draggedZone.zoneId) {
                    const newPoints = z.points.map(p => ({
                        x: Math.round(p.x + dx),
                        y: Math.round(p.y + dy)
                    }));
                    return { ...z, points: newPoints };
                }
                return z;
            });
            setDraggedZone({ ...draggedZone, offset: { x, y } });
            onZonesChange(updatedZones);
        } else {
            // Hover detection
            setHoveredPoint(getPointAt(x, y));
            setHoveredZoneId(getZoneAt(x, y));
        }
    };

    // Handle mouse up
    const handleMouseUp = () => {
        setDraggedPoint(null);
        setDraggedZone(null);
    };

    // Handle mouse leave
    const handleMouseLeave = () => {
        setMousePos(null);
        setDraggedPoint(null);
        setDraggedZone(null);
        setHoveredPoint(null);
        setHoveredZoneId(null);
    };

    // Handle right-click to remove last point
    const handleContextMenu = (e: React.MouseEvent<HTMLCanvasElement>) => {
        e.preventDefault();
        if (!activeZoneId) return;

        const updatedZones = zones.map((zone) => {
            if (zone.id === activeZoneId && zone.points.length > 0) {
                return {
                    ...zone,
                    points: zone.points.slice(0, -1),
                };
            }
            return zone;
        });

        onZonesChange(updatedZones);
    };

    if (!imageLoaded) {
        return (
            <div className="flex-1 flex items-center justify-center bg-primary-color border border-primary-border rounded-xl">
                <div className="text-secondary-text">Loading frame...</div>
            </div>
        );
    }

    // Dynamic cursor
    const getCursor = () => {
        if (draggedPoint) return "grabbing";
        if (hoveredPoint) return "grab";
        if (activeZoneId) return "crosshair";
        return "default";
    };

    return (
        <div
            ref={containerRef}
            className="flex-1 flex items-center justify-center p-4 bg-primary-color border border-primary-border rounded-xl overflow-hidden"
        >
            <canvas
                ref={canvasRef}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseLeave}
                onDoubleClick={handleDoubleClick}
                onContextMenu={handleContextMenu}
                className="rounded-lg shadow-2xl transition-shadow duration-300"
                style={{
                    maxWidth: "100%",
                    maxHeight: "100%",
                    cursor: getCursor()
                }}
            />
        </div>
    );
}
