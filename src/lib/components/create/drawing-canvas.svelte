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
		direction?: 'both' | 'in' | 'out'; // Crossing direction for line zones
	}
</script>

<script lang="ts">
	import { hexToRgba, pickZoneColor } from '$lib/zone-colors';

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
		onBeforeEdit?: () => void;
		currentPoints?: Point[];
		isDrawing?: boolean;
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
		onZoneUpdated,
		onBeforeEdit,
		currentPoints = $bindable([]),
		isDrawing = $bindable(false)
	}: Props = $props();

	let canvas: HTMLCanvasElement | undefined = $state();

	let currentMousePos = $state<Point | null>(null);

	// Color the next-to-be-created zone will use (preview during drawing)
	let nextColor = $derived(
		pickZoneColor(zones.map((z) => z.color).filter((c): c is string => !!c))
	);

	// Editing state
	let draggingPointIndex = $state<number | null>(null);
	let hoveredPointIndex = $state<number | null>(null);
	let hoveredEdge = $state<{ edgeIndex: number; point: Point } | null>(null);

	// Derived cursor style
	let cursor = $derived.by(() => {
		if (draggingPointIndex !== null) return 'cursor-grabbing';
		if (hoveredPointIndex !== null) return 'cursor-grab';
		if (hoveredEdge !== null) return 'cursor-copy';
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

	function getEdgeUnderCursor(
		x: number,
		y: number,
		zone: Zone
	): { edgeIndex: number; point: Point } | null {
		const hitRadius = 8 * (videoWidth / width);
		const pts = zone.points;
		if (pts.length < 2) return null;
		const segmentCount = zone.type === 'polygon' ? pts.length : pts.length - 1;

		for (let i = 0; i < segmentCount; i++) {
			const a = pts[i];
			const b = pts[(i + 1) % pts.length];
			const dx = b.x - a.x;
			const dy = b.y - a.y;
			const lenSq = dx * dx + dy * dy;
			if (lenSq === 0) continue;

			let t = ((x - a.x) * dx + (y - a.y) * dy) / lenSq;
			// Avoid inserting too close to existing endpoints
			if (t < 0.1 || t > 0.9) continue;

			const px = a.x + t * dx;
			const py = a.y + t * dy;
			const dist = Math.sqrt((x - px) * (x - px) + (y - py) * (y - py));
			if (dist <= hitRadius) {
				return { edgeIndex: i, point: { x: px, y: py } };
			}
		}
		return null;
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
			const zoneColor = zone.color || '#fbbd05';

			ctx.beginPath();
			ctx.lineWidth = isSelected ? lineWidth * 1.2 : lineWidth;
			ctx.strokeStyle = isSelected ? zoneColor : hexToRgba(zoneColor, 0.6);
			ctx.fillStyle = isSelected ? hexToRgba(zoneColor, 0.2) : hexToRgba(zoneColor, 0.1);

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

				// Draw A/B indicators for lines (only for the active selection to reduce clutter, or all if preferred. Let's do all for clarity)
				if (zone.points.length >= 2) {
					const p1 = zone.points[0];
					const p2 = zone.points[zone.points.length - 1]; // Use first and last point for overall direction

					// Calculate direction vector
					const dx = p2.x - p1.x;
					const dy = p2.y - p1.y;
					const len = Math.sqrt(dx * dx + dy * dy);

					if (len > 0) {
						// Normalize direction vector
						const nx = dx / len;
						const ny = dy / len;

						// Calculate normal vectors (perpendicular)
						// Right side (B)
						const normRx = -ny;
						const normRy = nx;
						// Left side (A)
						const normLx = ny;
						const normLy = -nx;

						// Midpoint of the line
						const midX = (p1.x + p2.x) / 2;
						const midY = (p1.y + p2.y) / 2;

						// Distance to place text away from the line
						const offset = 20 * scale;

						// Setup text styling
						ctx.font = `bold ${16 * scale}px sans-serif`;
						ctx.textAlign = 'center';
						ctx.textBaseline = 'middle';

						// Draw 'A' (Left side)
						const ax = midX + normLx * offset;
						const ay = midY + normLy * offset;
						ctx.fillStyle = '#ffffff';
						ctx.strokeStyle = '#000000';
						ctx.lineWidth = 2 * scale;
						ctx.strokeText('A', ax, ay);
						ctx.fillText('A', ax, ay);

						// Draw 'B' (Right side)
						const bx = midX + normRx * offset;
						const by = midY + normRy * offset;
						ctx.fillStyle = '#ffffff';
						ctx.strokeStyle = '#000000';
						ctx.lineWidth = 2 * scale;
						ctx.strokeText('B', bx, by);
						ctx.fillText('B', bx, by);
					}
				}
			}

			// Draw vertices ONLY for selected zone
			if (isSelected) {
				ctx.lineWidth = scale; // Thin border for handles
				ctx.strokeStyle = zoneColor;

				zone.points.forEach((point, index) => {
					const isHovered = hoveredPointIndex === index;
					const currentHandleSize = isHovered ? handleSize * 1.5 : handleSize;

					ctx.beginPath();
					ctx.arc(point.x, point.y, currentHandleSize / 2, 0, 2 * Math.PI);
					ctx.fillStyle = '#ffffff';
					ctx.fill();
					ctx.stroke();
				});

				// Ghost dot indicating where a new vertex would be inserted
				if (hoveredEdge && draggingPointIndex === null) {
					ctx.beginPath();
					ctx.arc(hoveredEdge.point.x, hoveredEdge.point.y, handleSize / 2, 0, 2 * Math.PI);
					ctx.fillStyle = hexToRgba(zoneColor, 0.6);
					ctx.fill();
					ctx.strokeStyle = '#ffffff';
					ctx.lineWidth = scale;
					ctx.stroke();
				}
			}
		});

		// 2. Draw CURRENT drawing in progress
		if (currentPoints.length > 0) {
			ctx.beginPath();
			ctx.lineWidth = lineWidth;
			ctx.strokeStyle = nextColor;
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

				// Draw A/B for elastic line if in line mode
				if (drawingMode === 'line' && currentPoints.length === 1) {
					const p1 = currentPoints[0];
					const dx = targetX - p1.x;
					const dy = targetY - p1.y;
					const len = Math.sqrt(dx * dx + dy * dy);

					if (len > 0) {
						const nx = dx / len;
						const ny = dy / len;
						const normRx = -ny,
							normRy = nx;
						const normLx = ny,
							normLy = -nx;

						const midX = (p1.x + targetX) / 2;
						const midY = (p1.y + targetY) / 2;
						const offset = 20 * scale;

						ctx.font = `bold ${16 * scale}px sans-serif`;
						ctx.textAlign = 'center';
						ctx.textBaseline = 'middle';
						ctx.lineWidth = 2 * scale;

						ctx.strokeText('A', midX + normLx * offset, midY + normLy * offset);
						ctx.fillText('A', midX + normLx * offset, midY + normLy * offset);

						ctx.strokeText('B', midX + normRx * offset, midY + normRy * offset);
						ctx.fillText('B', midX + normRx * offset, midY + normRy * offset);
					}
				}
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
					onBeforeEdit?.();
					draggingPointIndex = pointIndex;
					return;
				}

				// 1b. Check if clicking on an edge -> insert new vertex and start dragging it
				const edge = getEdgeUnderCursor(x, y, selectedZone);
				if (edge) {
					onBeforeEdit?.();
					const newPoints = [...selectedZone.points];
					newPoints.splice(edge.edgeIndex + 1, 0, edge.point);
					onZoneUpdated(selectedZoneId, newPoints);
					draggingPointIndex = edge.edgeIndex + 1;
					hoveredEdge = null;
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

		// Check for hover over vertices / edges if a zone is selected
		if (selectedZoneId && !isDrawing && currentPoints.length === 0) {
			const selectedZone = zones.find((z) => z.id === selectedZoneId);
			if (selectedZone) {
				const pointIndex = getPointUnderCursor(x, y, selectedZone.points);
				hoveredPointIndex = pointIndex !== -1 ? pointIndex : null;
				hoveredEdge = pointIndex === -1 ? getEdgeUnderCursor(x, y, selectedZone) : null;
			}
		} else {
			hoveredPointIndex = null;
			hoveredEdge = null;
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
