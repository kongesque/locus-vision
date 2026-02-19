<script lang="ts" module>
	export interface Point {
		x: number;
		y: number;
	}

	export interface Zone {
		id: string;
		points: Point[];
		type: 'polygon' | 'line';
		name: string;
		classes: string[]; // Selected COCO classes for detection
		color?: string; // Optional color for future use
	}
</script>

<script lang="ts">
	import { onMount } from 'svelte';

	interface Props {
		width: number;
		height: number;
		videoWidth: number;
		videoHeight: number;
		zones: Zone[];
		selectedZoneId: string | null;
		drawingMode: 'polygon' | 'line';
		onZoneCreated: (points: Point[]) => void;
		onZoneSelected: (id: string | null) => void;
		onZoneUpdated: (id: string, newPoints: Point[]) => void;
	}

	let {
		width,
		height,
		videoWidth,
		videoHeight,
		zones,
		selectedZoneId,
		drawingMode,
		onZoneCreated,
		onZoneSelected,
		onZoneUpdated
	}: Props = $props();

	let canvas: HTMLCanvasElement | undefined = $state();

	// Current drawing state (for NEW zone)
	let currentPoints = $state<Point[]>([]);
	let isDrawing = $state(false);
	let currentMousePos = $state<Point | null>(null);

	// Editing state
	let draggingPointIndex = $state<number | null>(null);
	let hoveredPointIndex = $state<number | null>(null);

	// Derived cursor style
	let cursor = $derived.by(() => {
		if (draggingPointIndex !== null) return 'cursor-grabbing';
		if (hoveredPointIndex !== null) return 'cursor-grab';
		if (selectedZoneId) return 'cursor-default';
		return 'cursor-crosshair';
	});

	function getScaledCoordinate(e: MouseEvent) {
		if (!canvas) return { x: 0, y: 0 };
		const rect = canvas.getBoundingClientRect();

		const x = e.clientX - rect.left;
		const y = e.clientY - rect.top;

		const ratioX = videoWidth / width;
		const ratioY = videoHeight / height;

		return {
			x: x * ratioX,
			y: y * ratioY,
			displayX: x,
			displayY: y
		};
	}

	function getPointUnderCursor(x: number, y: number, zonePoints: Point[]) {
		const hitRadius = 10 * (videoWidth / width);
		return zonePoints.findIndex((p) => {
			const dx = x - p.x;
			const dy = y - p.y;
			return Math.sqrt(dx * dx + dy * dy) <= hitRadius;
		});
	}

	function isPointInPolygon(x: number, y: number, points: Point[]) {
		let inside = false;
		for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
			const xi = points[i].x,
				yi = points[i].y;
			const xj = points[j].x,
				yj = points[j].y;

			const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
			if (intersect) inside = !inside;
		}
		return inside;
	}

	$effect(() => {
		// Redraw whenever dependencies change
		draw();
	});

	function draw() {
		if (!canvas) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		ctx.clearRect(0, 0, canvas.width, canvas.height);

		if (canvas.width !== videoWidth || canvas.height !== videoHeight) {
			canvas.width = videoWidth;
			canvas.height = videoHeight;
		}

		const scale = videoWidth / width;
		const lineWidth = 2.5 * scale;
		const handleSize = 8 * scale;

		// 1. Draw ALL saved zones
		zones.forEach((zone) => {
			if (zone.points.length === 0) return;
			const isSelected = zone.id === selectedZoneId;

			ctx.beginPath();
			ctx.lineWidth = isSelected ? lineWidth * 1.2 : lineWidth;
			ctx.strokeStyle = isSelected ? '#fbbd05' : 'rgba(251, 189, 5, 0.6)';
			ctx.fillStyle = isSelected ? 'rgba(251, 189, 5, 0.2)' : 'rgba(251, 189, 5, 0.1)';

			ctx.moveTo(zone.points[0].x, zone.points[0].y);
			for (let i = 1; i < zone.points.length; i++) {
				ctx.lineTo(zone.points[i].x, zone.points[i].y);
			}

			if (zone.type === 'polygon') {
				ctx.closePath();
				ctx.stroke();
				ctx.fill();
			} else {
				ctx.stroke();
			}

			// Draw vertices ONLY for selected zone
			if (isSelected) {
				ctx.lineWidth = scale; // Thin border for handles

				zone.points.forEach((point, index) => {
					const isHovered = hoveredPointIndex === index;
					const currentHandleSize = isHovered ? handleSize * 1.5 : handleSize;

					ctx.beginPath();
					ctx.arc(point.x, point.y, currentHandleSize / 2, 0, 2 * Math.PI);
					ctx.fillStyle = '#ffffff';
					ctx.fill();
					ctx.stroke();
				});
			}
		});

		// 2. Draw CURRENT drawing in progress
		if (currentPoints.length > 0) {
			ctx.beginPath();
			ctx.lineWidth = lineWidth;
			ctx.strokeStyle = '#fbbd05';
			ctx.moveTo(currentPoints[0].x, currentPoints[0].y);

			for (let i = 1; i < currentPoints.length; i++) {
				ctx.lineTo(currentPoints[i].x, currentPoints[i].y);
			}

			// Elastic line
			if (currentMousePos) {
				let targetX = currentMousePos.x;
				let targetY = currentMousePos.y;

				// Snap to start (ONLY for polygon)
				if (drawingMode === 'polygon' && currentPoints.length >= 2) {
					const startPoint = currentPoints[0];
					const hitRadius = 15 * scale;
					const dx = currentMousePos.x - startPoint.x;
					const dy = currentMousePos.y - startPoint.y;
					if (Math.sqrt(dx * dx + dy * dy) <= hitRadius) {
						targetX = startPoint.x;
						targetY = startPoint.y;
					}
				}
				ctx.lineTo(targetX, targetY);
			}

			ctx.stroke();

			// Draw vertices for current drawing
			ctx.fillStyle = '#ffffff';
			ctx.lineWidth = scale;
			currentPoints.forEach((point) => {
				ctx.beginPath();
				ctx.arc(point.x, point.y, handleSize / 2, 0, 2 * Math.PI);
				ctx.fill();
				ctx.stroke();
			});
		}
	}

	function handleMouseDown(e: MouseEvent) {
		const { x, y } = getScaledCoordinate(e);

		// A. If we are currently drawing a NEW polygon/line
		if (isDrawing || currentPoints.length > 0) {
			// Line Mode
			if (drawingMode === 'line') {
				// If we already have 1 point, this is the 2nd point -> Finish
				if (currentPoints.length === 1) {
					const newPoints = [...currentPoints, { x, y }];
					onZoneCreated(newPoints);
					currentPoints = [];
					isDrawing = false;
					return;
				}
			}

			// Polygon Mode
			else {
				// Check close condition
				if (currentPoints.length >= 2) {
					const startPoint = currentPoints[0];
					const hitRadius = 15 * (videoWidth / width);
					const dx = x - startPoint.x;
					const dy = y - startPoint.y;

					if (Math.sqrt(dx * dx + dy * dy) <= hitRadius) {
						// Complete polygon
						onZoneCreated(currentPoints);
						currentPoints = [];
						isDrawing = false;
						return;
					}
				}
			}

			currentPoints = [...currentPoints, { x, y }];
			isDrawing = true;
			return;
		}

		// B. Editing Mode (Not drawing new)

		// 1. Check if clicking a handle of the SELECTED zone
		if (selectedZoneId) {
			const selectedZone = zones.find((z) => z.id === selectedZoneId);
			if (selectedZone) {
				const pointIndex = getPointUnderCursor(x, y, selectedZone.points);
				if (pointIndex !== -1) {
					draggingPointIndex = pointIndex;
					return;
				}
			}
		}

		// 2. Check if clicking on ANY zone body (Selection)
		// Check in reverse order (topmost first)
		for (let i = zones.length - 1; i >= 0; i--) {
			if (isPointInPolygon(x, y, zones[i].points)) {
				onZoneSelected(zones[i].id);
				return;
			}
		}

		// 3. Clicked empty space -> Deselect
		if (selectedZoneId) {
			onZoneSelected(null);
			return;
		}

		// 4. Start new drawing
		currentPoints = [{ x, y }];
		isDrawing = true;
	}

	function handleMouseMove(e: MouseEvent) {
		const { x, y } = getScaledCoordinate(e);

		if (draggingPointIndex !== null && selectedZoneId) {
			// Update the point in the selected zone
			const selectedZone = zones.find((z) => z.id === selectedZoneId);
			if (selectedZone) {
				const newPoints = [...selectedZone.points];
				newPoints[draggingPointIndex] = { x, y };
				onZoneUpdated(selectedZoneId, newPoints);
			}
			return;
		}

		// Check for hover over vertices if a zone is selected
		if (selectedZoneId) {
			const selectedZone = zones.find((z) => z.id === selectedZoneId);
			if (selectedZone) {
				const pointIndex = getPointUnderCursor(x, y, selectedZone.points);
				hoveredPointIndex = pointIndex !== -1 ? pointIndex : null;
			}
		} else {
			hoveredPointIndex = null;
		}

		// Just update mouse pos for elastic line
		currentMousePos = { x, y };
	}

	function handleMouseUp() {
		if (draggingPointIndex !== null) {
			draggingPointIndex = null;
		}
	}

	function handleMouseLeave() {
		handleMouseUp();
	}
</script>

<div class="absolute top-0 left-0" style="width: {width}px; height: {height}px;">
	<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
	<canvas
		bind:this={canvas}
		style="width: 100%; height: 100%;"
		class={cursor}
		onmousedown={handleMouseDown}
		onmousemove={handleMouseMove}
		onmouseup={handleMouseUp}
		onmouseleave={handleMouseLeave}
	></canvas>
</div>
