<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import {
		Activity,
		Download,
		Calendar,
		Map,
		BarChart3,
		Users,
		Clock,
		TrendingUp
	} from '@lucide/svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	let selectedCamera = $state(untrack(() => data.cameras?.[0]?.id || ''));
	let timeRange = $state('7d');
	let isLoading = $state(false);

	let exportData = $state<any[]>([]);
	let heatmapPoints = $state<any[]>([]);

	interface PeakHoursData {
		hours: { hour: number; count: number; avg_dwell: number }[];
		peak_hour: number;
		peak_count: number;
		total_events: number;
	}
	let peakHoursData = $state<PeakHoursData | null>(null);

	let canvasElem = $state<HTMLCanvasElement>();
	let canvasWidth = $state(640);
	let canvasHeight = $state(480);

	// Summary stats
	let totalVisitors = $derived(exportData.reduce((acc, row) => acc + (row.unique_objects || 0), 0));
	let avgDwell = $derived(
		exportData.length > 0
			? exportData.reduce((acc, row) => acc + (row.avg_dwell_time || 0), 0) / exportData.length
			: 0
	);
	let maxHourCount = $derived(
		peakHoursData ? Math.max(...peakHoursData.hours.map((h) => h.count), 1) : 1
	);

	function formatHour(h: number): string {
		if (h === 0) return '12a';
		if (h < 12) return `${h}a`;
		if (h === 12) return '12p';
		return `${h - 12}p`;
	}

	function formatHourLong(h: number): string {
		if (h === 0) return '12:00 AM';
		if (h < 12) return `${h}:00 AM`;
		if (h === 12) return '12:00 PM';
		return `${h - 12}:00 PM`;
	}

	async function loadAnalytics() {
		if (!selectedCamera) return;
		isLoading = true;

		try {
			// Calculate dates
			const end = new Date();
			const start = new Date();
			if (timeRange === '24h') start.setHours(start.getHours() - 24);
			else if (timeRange === '7d') start.setDate(start.getDate() - 7);
			else if (timeRange === '30d') start.setDate(start.getDate() - 30);

			const startIso = start.toISOString();
			const endIso = end.toISOString();

			// 1. Fetch Aggregated Data
			const resExport = await fetch(
				`http://127.0.0.1:8000/api/analytics/export?camera_id=${selectedCamera}&start_time=${startIso}&end_time=${endIso}&format=json`
			);
			if (resExport.ok) {
				const json = await resExport.json();
				exportData = json.data || [];
			}

			// 2. Fetch Heatmap Data
			const resHeatmap = await fetch(
				`http://127.0.0.1:8000/api/analytics/heatmap?camera_id=${selectedCamera}&start_time=${startIso}&end_time=${endIso}`
			);
			if (resHeatmap.ok) {
				const json = await resHeatmap.json();
				heatmapPoints = json.points || [];
				drawHeatmap();
			}

			// 3. Fetch Peak Hours Data
			const resPeak = await fetch(
				`http://127.0.0.1:8000/api/analytics/peak-hours?camera_id=${selectedCamera}&start_time=${startIso}&end_time=${endIso}`
			);
			if (resPeak.ok) {
				peakHoursData = await resPeak.json();
			}
		} catch (e) {
			console.error('Failed to load analytics', e);
		} finally {
			isLoading = false;
		}
	}

	function drawHeatmap() {
		if (!canvasElem) return;
		const ctx = canvasElem.getContext('2d');
		if (!ctx) return;

		// Clear canvas
		ctx.clearRect(0, 0, canvasWidth, canvasHeight);

		// Draw a dark background
		ctx.fillStyle = '#0f172a'; // slate-900
		ctx.fillRect(0, 0, canvasWidth, canvasHeight);

		if (heatmapPoints.length === 0) {
			ctx.fillStyle = '#475569';
			ctx.font = '14px sans-serif';
			ctx.textAlign = 'center';
			ctx.fillText('No movement data for this period', canvasWidth / 2, canvasHeight / 2);
			return;
		}

		// Global composite operation to blend overlaps
		ctx.globalCompositeOperation = 'screen';

		// Draw spaghetti maps / heat points
		heatmapPoints.forEach((pt) => {
			const x = pt.x;
			const y = pt.y;

			// Create radial gradient for each point
			const radgrad = ctx.createRadialGradient(x, y, 0, x, y, 15);
			radgrad.addColorStop(0, 'rgba(239, 68, 68, 0.4)'); // Red center
			radgrad.addColorStop(0.5, 'rgba(249, 115, 22, 0.1)'); // Orange mid
			radgrad.addColorStop(1, 'rgba(0, 0, 0, 0)'); // Transparent edge

			ctx.fillStyle = radgrad;
			ctx.beginPath();
			ctx.arc(x, y, 15, 0, Math.PI * 2, true);
			ctx.fill();
		});

		// Reset composite
		ctx.globalCompositeOperation = 'source-over';
	}

	onMount(() => {
		if (selectedCamera) {
			loadAnalytics();
		}
	});

	function handleDownloadCsv() {
		if (!selectedCamera) return;
		const end = new Date();
		const start = new Date();
		if (timeRange === '24h') start.setHours(start.getHours() - 24);
		else if (timeRange === '7d') start.setDate(start.getDate() - 7);
		else if (timeRange === '30d') start.setDate(start.getDate() - 30);

		const url = `http://127.0.0.1:8000/api/analytics/export?camera_id=${selectedCamera}&start_time=${start.toISOString()}&end_time=${end.toISOString()}&format=csv`;
		window.open(url, '_blank');
	}
</script>

<svelte:head>
	<title>Historical Analytics · Locus</title>
</svelte:head>

<div class="relative flex flex-1 flex-col gap-4 p-4">
	<!-- Header -->
	<div class="flex flex-col justify-between gap-4 md:flex-row md:items-center">
		<div>
			<h1 class="text-2xl font-bold tracking-tight">Historical Analytics</h1>
			<p class="text-muted-foreground">View aggregated zone telemetry and movement heatmaps.</p>
		</div>

		<div class="flex items-center gap-3">
			<select
				class="flex h-10 w-[200px] items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
				bind:value={selectedCamera}
				onchange={loadAnalytics}
			>
				{#if data.cameras?.length === 0}
					<option value="">No cameras available</option>
				{/if}
				{#each data.cameras as cam}
					<option value={cam.id}>{cam.name || cam.id}</option>
				{/each}
			</select>

			<select
				class="flex h-10 w-[140px] items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:ring-2 focus:ring-ring focus:outline-none disabled:cursor-not-allowed disabled:opacity-50"
				bind:value={timeRange}
				onchange={loadAnalytics}
			>
				<option value="24h">Last 24 Hours</option>
				<option value="7d">Last 7 Days</option>
				<option value="30d">Last 30 Days</option>
			</select>

			<button
				class="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium whitespace-nowrap text-primary-foreground shadow transition-colors hover:bg-primary/90 focus-visible:ring-1 focus-visible:ring-ring focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
				onclick={handleDownloadCsv}
			>
				<Download class="mr-2 h-4 w-4" /> Export CSV
			</button>
		</div>
	</div>

	{#if isLoading}
		<div class="flex h-64 items-center justify-center rounded-xl border border-dashed">
			<Activity class="h-8 w-8 animate-pulse text-muted-foreground" />
		</div>
	{:else}
		<!-- KPIs -->
		<div class="grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
			<div
				class="rounded-xl border bg-gradient-to-br from-card to-muted/50 text-card-foreground shadow transition-all duration-300 hover:scale-[1.02] hover:shadow-md"
			>
				<div class="flex flex-row items-center justify-between space-y-0 p-6 pb-2">
					<h3 class="text-sm font-medium tracking-tight">Total Detections</h3>
					<Users class="h-4 w-4 text-primary" />
				</div>
				<div class="p-6 pt-0">
					<div class="text-2xl font-bold">{totalVisitors.toLocaleString()}</div>
					<p class="text-xs text-muted-foreground">Unique objects tracked</p>
				</div>
			</div>
			<div
				class="rounded-xl border bg-gradient-to-br from-card to-muted/50 text-card-foreground shadow transition-all duration-300 hover:scale-[1.02] hover:shadow-md"
			>
				<div class="flex flex-row items-center justify-between space-y-0 p-6 pb-2">
					<h3 class="text-sm font-medium tracking-tight">Avg Dwell Time</h3>
					<Clock class="h-4 w-4 text-primary" />
				</div>
				<div class="p-6 pt-0">
					<div class="text-2xl font-bold">{avgDwell.toFixed(1)}s</div>
					<p class="text-xs text-muted-foreground">Average time spent in zones</p>
				</div>
			</div>
			<div
				class="rounded-xl border bg-gradient-to-br from-card to-muted/50 text-card-foreground shadow transition-all duration-300 hover:scale-[1.02] hover:shadow-md"
			>
				<div class="flex flex-row items-center justify-between space-y-0 p-6 pb-2">
					<h3 class="text-sm font-medium tracking-tight">Data Points</h3>
					<BarChart3 class="h-4 w-4 text-primary" />
				</div>
				<div class="p-6 pt-0">
					<div class="text-2xl font-bold">{exportData.length}</div>
					<p class="text-xs text-muted-foreground">Aggregated hourly buckets</p>
				</div>
			</div>
			<div
				class="rounded-xl border bg-gradient-to-br from-amber-500/10 to-card text-card-foreground shadow transition-all duration-300 hover:scale-[1.02] hover:shadow-md"
			>
				<div class="flex flex-row items-center justify-between space-y-0 p-6 pb-2">
					<h3 class="text-sm font-medium tracking-tight">Peak Hour</h3>
					<TrendingUp class="h-4 w-4 text-amber-500" />
				</div>
				<div class="p-6 pt-0">
					{#if peakHoursData && peakHoursData.total_events > 0}
						<div class="text-2xl font-bold">{formatHourLong(peakHoursData.peak_hour)}</div>
						<p class="text-xs text-muted-foreground">
							{peakHoursData.peak_count} detections at peak
						</p>
					{:else}
						<div class="text-2xl font-bold">—</div>
						<p class="text-xs text-muted-foreground">No traffic data yet</p>
					{/if}
				</div>
			</div>
		</div>

		<!-- Peak Hours Chart -->
		<div class="rounded-xl border bg-card text-card-foreground shadow">
			<div class="flex flex-col space-y-1.5 border-b p-6">
				<h3 class="flex items-center gap-2 leading-none font-semibold tracking-tight">
					<TrendingUp class="h-4 w-4 text-amber-500" /> Peak Hours Distribution
				</h3>
				<p class="text-sm text-muted-foreground">Zone traffic by hour of day</p>
			</div>
			<div class="p-6">
				{#if peakHoursData && peakHoursData.total_events > 0}
					<div class="flex h-[220px] items-end gap-[3px]">
						{#each peakHoursData.hours as h (h.hour)}
							{@const pct = (h.count / maxHourCount) * 100}
							{@const isPeak = h.hour === peakHoursData.peak_hour}
							<div class="group relative flex flex-1 flex-col items-center justify-end">
								<!-- Tooltip -->
								<div
									class="pointer-events-none absolute -top-14 left-1/2 z-10 min-w-max -translate-x-1/2 scale-0 rounded-md border bg-popover px-2.5 py-1.5 text-xs shadow-md transition-transform group-hover:scale-100"
								>
									<p class="font-semibold">{formatHourLong(h.hour)}</p>
									<p class="text-muted-foreground">
										{h.count} detections · {h.avg_dwell.toFixed(1)}s avg
									</p>
								</div>
								<!-- Bar -->
								<div
									class="w-full cursor-pointer rounded-t-sm transition-all duration-500 ease-out group-hover:opacity-90 {isPeak
										? 'bg-gradient-to-t from-amber-600 to-amber-400 shadow-[0_0_12px_rgba(245,158,11,0.4)]'
										: 'bg-primary/60 group-hover:bg-primary/80'}"
									style="height: {Math.max(
										pct,
										h.count > 0 ? 4 : 1
									)}%; animation: barGrow 0.6s ease-out {h.hour * 30}ms both;"
								></div>
								<!-- Label -->
								<span
									class="mt-2 text-[10px] tabular-nums {isPeak
										? 'font-bold text-amber-500'
										: 'text-muted-foreground'}"
								>
									{formatHour(h.hour)}
								</span>
							</div>
						{/each}
					</div>
				{:else}
					<div class="flex h-[220px] flex-col items-center justify-center text-center">
						<BarChart3 class="mb-3 h-10 w-10 text-muted-foreground/30" />
						<p class="text-sm text-muted-foreground">No traffic data for this period</p>
						<p class="mt-1 text-xs text-muted-foreground">
							Zone events will appear here once detected
						</p>
					</div>
				{/if}
			</div>
		</div>

		<!-- Main Charts Area -->
		<div class="grid grid-cols-1 gap-6 lg:grid-cols-2">
			<!-- Heatmap / Spaghetti Map -->
			<div class="col-span-1 flex flex-col rounded-xl border bg-card text-card-foreground shadow">
				<div class="flex flex-col space-y-1.5 border-b p-6">
					<h3 class="flex items-center gap-2 leading-none font-semibold tracking-tight">
						<Map class="h-4 w-4 text-blue-500" /> Movement Heatmap
					</h3>
				</div>
				<div
					class="relative flex min-h-[480px] flex-1 items-center justify-center overflow-hidden rounded-b-xl bg-zinc-950/80 p-0 shadow-[inset_0_0_40px_rgba(59,130,246,0.1)] ring-1 ring-white/5"
				>
					<canvas
						bind:this={canvasElem}
						width={canvasWidth}
						height={canvasHeight}
						class="max-w-full drop-shadow-xl"
					></canvas>

					<div
						class="absolute bottom-4 left-4 flex items-center gap-2 rounded-lg border border-white/10 bg-black/60 px-3 py-1.5 backdrop-blur"
					>
						<span class="text-[10px] text-zinc-400">Low</span>
						<div
							class="h-2 w-24 rounded-full bg-gradient-to-r from-orange-500/10 via-orange-500/50 to-red-500"
						></div>
						<span class="text-[10px] text-zinc-400">High Density</span>
					</div>
				</div>
			</div>

			<!-- Aggregated List -->
			<div class="col-span-1 rounded-xl border bg-card text-card-foreground shadow">
				<div class="flex flex-col space-y-1.5 border-b p-6">
					<h3 class="flex items-center gap-2 leading-none font-semibold tracking-tight">
						<Calendar class="h-4 w-4 text-purple-500" /> Hourly Zone Telemetry
					</h3>
					<p class="text-sm text-muted-foreground">Recent data buckets</p>
				</div>
				<div class="p-0">
					<div class="relative max-h-[480px] w-full overflow-auto">
						<table class="w-full caption-bottom text-sm">
							<thead class="sticky top-0 bg-muted/50 [&_tr]:border-b">
								<tr
									class="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted"
								>
									<th class="h-10 px-4 text-left align-middle font-medium text-muted-foreground"
										>Time Hour</th
									>
									<th class="h-10 px-4 text-left align-middle font-medium text-muted-foreground"
										>Zone</th
									>
									<th class="h-10 px-4 text-left align-middle font-medium text-muted-foreground"
										>Objects</th
									>
									<th class="h-10 px-4 text-left align-middle font-medium text-muted-foreground"
										>Avg Dwell</th
									>
								</tr>
							</thead>
							<tbody class="bg-card [&_tr:last-child]:border-0">
								{#each exportData.slice(0, 50) as row}
									<tr
										class="border-b transition-colors hover:bg-muted/50 data-[state=selected]:bg-muted"
									>
										<td class="p-4 align-middle font-mono text-xs"
											>{new Date(row.bucket).toLocaleString()}</td
										>
										<td class="p-4 align-middle">
											<span
												class="inline-flex items-center rounded-full border border-transparent bg-secondary px-2.5 py-0.5 text-xs font-semibold text-secondary-foreground transition-colors hover:bg-secondary/80 focus:ring-2 focus:ring-ring focus:ring-offset-2 focus:outline-none"
											>
												{row.zone_id}
											</span>
										</td>
										<td class="p-4 align-middle font-semibold">{row.unique_objects}</td>
										<td class="p-4 align-middle text-muted-foreground"
											>{row.avg_dwell_time?.toFixed(1) || '0.0'}s</td
										>
									</tr>
								{/each}
								{#if exportData.length === 0}
									<tr>
										<td colspan="4" class="p-4 text-center text-muted-foreground"
											>No data recorded for this period.</td
										>
									</tr>
								{/if}
							</tbody>
						</table>
					</div>
				</div>
			</div>
		</div>
	{/if}
</div>
