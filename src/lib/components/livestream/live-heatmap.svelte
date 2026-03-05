<script lang="ts">
	import { onMount, untrack } from 'svelte';

	interface Point {
		x: number;
		y: number;
		timestamp: number;
	}

	interface LiveHeatmapProps {
		points: Point[];
		width?: number;
		height?: number;
		maxAgeMs?: number;
		radius?: number;
		intensity?: number;
		show?: boolean;
	}

	let {
		points = [],
		width = 640,
		height = 480,
		maxAgeMs = 3000,
		radius = 30,
		intensity = 0.5,
		show = true
	}: LiveHeatmapProps = $props();

	let canvas: HTMLCanvasElement;
	let animationFrameId: number;

	// Local buffer of points to animate decaying
	let activePoints = $state<Point[]>([]);

	// When points are added to the prop, we add them to our local buffer
	// if they don't already exist (simple deep ish comparison or just append).
	// Actually, the easiest is to just accept an event-driven "addPoint" or
	// react to changes in the points array. If points prop is a streaming log:
	let lastPointsLength = 0;
	$effect(() => {
		if (points.length > lastPointsLength) {
			const newPts = points.slice(lastPointsLength);
			untrack(() => {
				activePoints = [...activePoints, ...newPts];
			});
		}
		lastPointsLength = points.length;
	});

	function drawHeatmap() {
		if (!canvas) return;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		// Clear canvas
		ctx.clearRect(0, 0, width, height);

		if (!show) {
			animationFrameId = requestAnimationFrame(drawHeatmap);
			return;
		}

		const now = performance.now(); // or Date.now(), assuming points use Date.now()
		// Let's assume points.timestamp is standard Date.now() timestamp from backend / frontend
		const currentTimestamp = Date.now();

		// Filter active points
		activePoints = activePoints.filter((p) => currentTimestamp - p.timestamp < maxAgeMs);

		ctx.globalCompositeOperation = 'screen'; // Use screen blending for heatmap effect

		for (const point of activePoints) {
			const age = currentTimestamp - point.timestamp;
			// Calculate opacity based on age (1.0 when new, 0.0 when expires)
			const lifeRatio = Math.max(0, 1 - age / maxAgeMs);
			const opacity = lifeRatio * intensity;

			const grad = ctx.createRadialGradient(point.x, point.y, 0, point.x, point.y, radius);
			// Center is intense red/orange, fading to transparent red
			grad.addColorStop(0, `rgba(255, 60, 0, ${opacity})`);
			grad.addColorStop(0.5, `rgba(255, 120, 0, ${opacity * 0.5})`);
			grad.addColorStop(1, `rgba(255, 120, 0, 0)`);

			ctx.fillStyle = grad;
			ctx.beginPath();
			ctx.arc(point.x, point.y, radius, 0, 2 * Math.PI);
			ctx.fill();
		}

		ctx.globalCompositeOperation = 'source-over';
		animationFrameId = requestAnimationFrame(drawHeatmap);
	}

	onMount(() => {
		drawHeatmap();
		return () => {
			if (animationFrameId) cancelAnimationFrame(animationFrameId);
		};
	});
</script>

<canvas
	bind:this={canvas}
	{width}
	{height}
	class="pointer-events-none absolute inset-0 size-full transition-opacity duration-300 {show
		? 'opacity-100'
		: 'opacity-0'}"
	style="object-fit: fill;"
></canvas>
