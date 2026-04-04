<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URL } from '$lib/api';
	import {
		Activity,
		Cpu,
		HardDrive,
		MemoryStick,
		Video,
		Camera,
		Database,
		Zap
	} from '@lucide/svelte';
	import { Card, CardContent, CardHeader, CardTitle } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Tabs, TabsContent, TabsList, TabsTrigger } from '$lib/components/ui/tabs';

	// Frigate-style detailed camera stats
	interface CameraStat {
		id: string;
		name: string;
		is_active: boolean;
		input_fps: number;
		process_fps: number;
		detect_fps: number;
		skipped_fps: number;
		dropped_frames: number;
		total_frames: number;
		inference_ms: number;
		cpu_percent?: number;
		memory_mb?: number;
	}

	// Frigate-style detector with percentiles
	interface DetectorStat {
		model_name: string;
		inference_speed: {
			p50: number;
			p90: number;
			p99: number;
		};
		total_inferences: number;
		avg_detections: number;
		detector_type: string;
	}

	interface ProcessStat {
		name: string;
		cpu_percent: number;
		memory_mb: number;
	}

	interface StorageStat {
		total: { used_gb: number; total_gb: number; percent: number };
		recordings: { size_gb: number; file_count: number };
		database: { size_mb: number };
		duckdb?: { size_mb: number };
		archives?: { size_gb: number };
		cache?: { size_mb: number };
	}

	interface SystemStat {
		cpu_percent: number;
		memory_percent: number;
		memory_used_mb: number;
		memory_total_mb: number;
		processes: ProcessStat[];
	}

	interface Stats {
		timestamp: number;
		system: SystemStat;
		storage: StorageStat;
		detector: DetectorStat;
		cameras: CameraStat[];
		summary: {
			active_cameras: number;
			total_cameras: number;
		};
	}

	let stats: Stats | null = $state(null);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;
	let lastUpdated = $state<Date | null>(null);
	let error = $state<string | null>(null);
	let activeTab = $state('cameras');

	async function fetchStats() {
		try {
			const res = await fetch(`${API_URL}/api/system/stats`);
			if (!res.ok) throw new Error(`HTTP ${res.status}`);
			stats = await res.json();
			lastUpdated = new Date();
			error = null;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to fetch stats';
			console.error('[System] Failed to fetch stats:', e);
		}
	}

	onMount(() => {
		fetchStats();
		refreshInterval = setInterval(fetchStats, 3000);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	function formatBytes(mb: number): string {
		if (mb > 1024 * 1024) {
			return `${(mb / 1024 / 1024).toFixed(2)} TB`;
		}
		if (mb > 1024) {
			return `${(mb / 1024).toFixed(1)} GB`;
		}
		return `${Math.round(mb)} MB`;
	}

	function getStatusColor(percent: number): string {
		if (percent < 50) return 'bg-emerald-500';
		if (percent < 80) return 'bg-amber-500';
		return 'bg-red-500';
	}

	function getFpsStatus(input: number, process: number): string {
		if (process < input * 0.5) return 'text-red-500';
		if (process < input * 0.8) return 'text-amber-500';
		return 'text-emerald-500';
	}
</script>

<svelte:head>
	<title>System · Locus</title>
</svelte:head>

<div class="relative flex flex-1 flex-col gap-4 p-4">
	<!-- Header -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">System</h1>
			<p class="mt-1 text-muted-foreground">Hardware usage and application performance metrics</p>
		</div>
		<div class="flex items-center gap-4">
			{#if error}
				<Badge variant="destructive">Error: {error}</Badge>
			{:else if lastUpdated}
				<span class="text-sm text-muted-foreground">
					Updated {lastUpdated.toLocaleTimeString()}
				</span>
			{/if}
			<div class="flex items-center gap-2 text-sm text-muted-foreground">
				<span class="relative flex h-2 w-2">
					<span
						class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"
					></span>
					<span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
				</span>
				Live
			</div>
		</div>
	</div>

	{#if !stats}
		<div class="flex h-64 items-center justify-center">
			<div class="flex animate-pulse items-center gap-2 text-muted-foreground">
				<Activity class="h-5 w-5 animate-spin" />
				Loading system metrics...
			</div>
		</div>
	{:else}
		<!-- Top Stats Cards (Frigate-style) -->
		<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
			<Card class="transition-all duration-300 hover:scale-[1.02] hover:shadow-md">
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">CPU Usage</CardTitle>
					<Cpu class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					<div class="text-2xl font-bold">{stats.system.cpu_percent.toFixed(1)}%</div>
					<div class="mt-2 h-2 w-full rounded-full bg-secondary">
						<div
							class="h-2 rounded-full transition-all duration-500 {getStatusColor(
								stats.system.cpu_percent
							)}"
							style="width: {stats.system.cpu_percent}%"
						></div>
					</div>
				</CardContent>
			</Card>

			<Card class="transition-all duration-300 hover:scale-[1.02] hover:shadow-md">
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">Memory</CardTitle>
					<MemoryStick class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					<div class="text-2xl font-bold">{stats.system.memory_percent.toFixed(1)}%</div>
					<p class="mt-1 text-xs text-muted-foreground">
						{formatBytes(stats.system.memory_used_mb)} / {formatBytes(stats.system.memory_total_mb)}
					</p>
					<div class="mt-2 h-2 w-full rounded-full bg-secondary">
						<div
							class="h-2 rounded-full transition-all duration-500 {getStatusColor(
								stats.system.memory_percent
							)}"
							style="width: {stats.system.memory_percent}%"
						></div>
					</div>
				</CardContent>
			</Card>

			<Card class="transition-all duration-300 hover:scale-[1.02] hover:shadow-md">
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">Storage</CardTitle>
					<HardDrive class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					{@const diskPercent = stats.storage?.total?.percent || 0}
					<div class="text-2xl font-bold">{diskPercent.toFixed(1)}%</div>
					<p class="mt-1 text-xs text-muted-foreground">
						{stats.storage?.total?.used_gb?.toFixed(1) || 0} GB / {stats.storage?.total?.total_gb?.toFixed(
							0
						) || 0} GB
					</p>
					<div class="mt-2 h-2 w-full rounded-full bg-secondary">
						<div
							class="h-2 rounded-full transition-all duration-500 {getStatusColor(diskPercent)}"
							style="width: {diskPercent}%"
						></div>
					</div>
				</CardContent>
			</Card>

			<Card class="transition-all duration-300 hover:scale-[1.02] hover:shadow-md">
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">Detector</CardTitle>
					<Zap class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					{#if stats.detector?.inference_speed}
						<div class="text-2xl font-bold">
							{(stats.detector.inference_speed.p50 || 0).toFixed(1)}ms
						</div>
						<p class="mt-1 text-xs text-muted-foreground">
							{stats.detector.model_name || 'yolo11n'} - {stats.detector.total_inferences?.toLocaleString() ||
								0} inferences
						</p>
						<div class="mt-2 flex gap-2 text-xs text-muted-foreground">
							<span>p90: {(stats.detector.inference_speed.p90 || 0).toFixed(1)}ms</span>
							<span>p99: {(stats.detector.inference_speed.p99 || 0).toFixed(1)}ms</span>
						</div>
					{:else}
						<div class="text-2xl font-bold">0.0ms</div>
						<p class="mt-1 text-xs text-muted-foreground">No detector data available</p>
					{/if}
				</CardContent>
			</Card>
		</div>

		<!-- Frigate-style Tabs -->
		<Tabs bind:value={activeTab} class="w-full">
			<TabsList class="grid w-full grid-cols-3 lg:w-[400px]">
				<TabsTrigger value="cameras">
					<Camera class="mr-2 h-4 w-4" />
					Cameras
				</TabsTrigger>
				<TabsTrigger value="processes">
					<Cpu class="mr-2 h-4 w-4" />
					Processes
				</TabsTrigger>
				<TabsTrigger value="storage">
					<Database class="mr-2 h-4 w-4" />
					Storage
				</TabsTrigger>
			</TabsList>

			<!-- Cameras Tab (Frigate-style) -->
			<TabsContent value="cameras">
				<Card>
					<CardHeader>
						<div class="flex items-center justify-between">
							<CardTitle>Camera Performance</CardTitle>
							<Badge variant="secondary">
								{stats.summary.active_cameras} active / {stats.summary.total_cameras} total
							</Badge>
						</div>
					</CardHeader>
					<CardContent>
						{#if stats.cameras.length === 0}
							<div class="py-8 text-center text-muted-foreground">
								<Video class="mx-auto mb-3 h-12 w-12 opacity-50" />
								<p>No cameras currently streaming</p>
								<p class="text-sm">Start a live stream to see camera metrics</p>
							</div>
						{:else}
							<div class="overflow-x-auto">
								<table class="w-full text-sm">
									<thead>
										<tr class="border-b text-left">
											<th class="pb-3 font-medium">Camera</th>
											<th class="pb-3 text-right font-medium">Status</th>
											<th class="pb-3 text-right font-medium">Input FPS</th>
											<th class="pb-3 text-right font-medium">Process FPS</th>
											<th class="pb-3 text-right font-medium">Detect FPS</th>
											<th class="pb-3 text-right font-medium">Skipped</th>
											<th class="pb-3 text-right font-medium">Inference</th>
										</tr>
									</thead>
									<tbody>
										{#each stats.cameras as cam}
											<tr class="border-b last:border-0">
												<td class="py-3">
													<div class="font-medium">{cam.name || cam.id.slice(0, 8)}</div>
													<div class="text-xs text-muted-foreground">{cam.id}</div>
												</td>
												<td class="py-3 text-right">
													{#if cam.is_active}
														<Badge class="bg-emerald-500 hover:bg-emerald-600">Active</Badge>
													{:else}
														<Badge variant="secondary">Inactive</Badge>
													{/if}
												</td>
												<td class="py-3 text-right font-mono"
													>{cam.input_fps?.toFixed(1) || '0.0'}</td
												>
												<td
													class="py-3 text-right font-mono {getFpsStatus(
														cam.input_fps || 0,
														cam.process_fps || 0
													)}"
												>
													{cam.process_fps?.toFixed(1) || '0.0'}
												</td>
												<td class="py-3 text-right font-mono"
													>{cam.detect_fps?.toFixed(1) || '0.0'}</td
												>
												<td class="py-3 text-right">
													{#if (cam.skipped_fps || 0) > 0}
														<span class="font-medium text-amber-500"
															>{cam.skipped_fps.toFixed(1)}/s</span
														>
													{:else}
														<span class="text-muted-foreground">-</span>
													{/if}
												</td>
												<td class="py-3 text-right font-mono"
													>{cam.inference_ms?.toFixed(1) || '0.0'}ms</td
												>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>

							<!-- Legend -->
							<div class="mt-4 flex gap-4 text-xs text-muted-foreground">
								<div class="flex items-center gap-1">
									<span class="h-2 w-2 rounded-full bg-emerald-500"></span>
									Normal performance
								</div>
								<div class="flex items-center gap-1">
									<span class="h-2 w-2 rounded-full bg-amber-500"></span>
									Processing lag
								</div>
								<div class="flex items-center gap-1">
									<span class="h-2 w-2 rounded-full bg-red-500"></span>
									Significant lag
								</div>
							</div>
						{/if}
					</CardContent>
				</Card>
			</TabsContent>

			<!-- Processes Tab -->
			<TabsContent value="processes">
				<Card>
					<CardHeader>
						<CardTitle>Process Resource Usage</CardTitle>
					</CardHeader>
					<CardContent>
						{#if !stats.system.processes || stats.system.processes.length === 0}
							<div class="py-8 text-center text-muted-foreground">
								<p>Process-level metrics not available</p>
							</div>
						{:else}
							<div class="space-y-4">
								{#each stats.system.processes as proc}
									<div class="flex items-center justify-between rounded-lg bg-muted p-3">
										<div>
											<div class="font-medium">{proc.name}</div>
											<div class="text-xs text-muted-foreground">
												{proc.memory_mb?.toFixed(1) || 0} MB
											</div>
										</div>
										<div class="flex items-center gap-4">
											<div class="text-right">
												<div class="text-sm font-medium">
													{proc.cpu_percent?.toFixed(1) || 0}% CPU
												</div>
												<div class="mt-1 h-1.5 w-24 rounded-full bg-secondary">
													<div
														class="h-full rounded-full {getStatusColor(proc.cpu_percent || 0)}"
														style="width: {Math.min(proc.cpu_percent || 0, 100)}%"
													></div>
												</div>
											</div>
										</div>
									</div>
								{/each}
							</div>
						{/if}
					</CardContent>
				</Card>
			</TabsContent>

			<!-- Storage Tab (Frigate-style breakdown) -->
			<TabsContent value="storage">
				<Card>
					<CardHeader>
						<CardTitle>Storage Breakdown</CardTitle>
					</CardHeader>
					<CardContent>
						<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
							<!-- Total Storage -->
							<div class="rounded-lg bg-muted p-4">
								<div class="mb-2 flex items-center justify-between">
									<span class="text-sm font-medium">Total Usage</span>
									<HardDrive class="h-4 w-4 text-muted-foreground" />
								</div>
								<div class="text-2xl font-bold">
									{stats.storage?.total?.percent?.toFixed(1) || 0}%
								</div>
								<div class="mt-1 text-xs text-muted-foreground">
									{stats.storage?.total?.used_gb?.toFixed(1) || 0} / {stats.storage?.total?.total_gb?.toFixed(
										0
									) || 0} GB
								</div>
								<div class="mt-3 h-2 w-full rounded-full bg-secondary">
									<div
										class="h-full rounded-full {getStatusColor(stats.storage?.total?.percent || 0)}"
										style="width: {stats.storage?.total?.percent || 0}%"
									></div>
								</div>
							</div>

							<!-- Recordings -->
							<div class="rounded-lg bg-muted p-4">
								<div class="mb-2 flex items-center justify-between">
									<span class="text-sm font-medium">Recordings</span>
									<Video class="h-4 w-4 text-muted-foreground" />
								</div>
								<div class="text-2xl font-bold">
									{stats.storage?.recordings?.size_gb?.toFixed(2) || 0} GB
								</div>
								<div class="mt-1 text-xs text-muted-foreground">
									{stats.storage?.recordings?.file_count?.toLocaleString() || 0} files
								</div>
							</div>

							<!-- Database -->
							<div class="rounded-lg bg-muted p-4">
								<div class="mb-2 flex items-center justify-between">
									<span class="text-sm font-medium">App DB (SQLite)</span>
									<Database class="h-4 w-4 text-muted-foreground" />
								</div>
								<div class="text-2xl font-bold">
									{stats.storage?.database?.size_mb?.toFixed(1) || 0} MB
								</div>
								<div class="mt-1 text-xs text-muted-foreground">State & configuration</div>
							</div>

							<!-- Analytics DB -->
							<div class="rounded-lg bg-muted p-4">
								<div class="mb-2 flex items-center justify-between">
									<span class="text-sm font-medium">Analytics DB (DuckDB)</span>
									<Database class="h-4 w-4 text-muted-foreground" />
								</div>
								<div class="text-2xl font-bold">
									{stats.storage?.duckdb?.size_mb?.toFixed(1) || 0} MB
								</div>
								<div class="mt-1 text-xs text-muted-foreground">Time-series telemetry</div>
							</div>

							<!-- Archives -->
							<div class="rounded-lg bg-muted p-4">
								<div class="mb-2 flex items-center justify-between">
									<span class="text-sm font-medium">Data Archives</span>
									<Database class="h-4 w-4 text-muted-foreground" />
								</div>
								<div class="text-2xl font-bold">
									{stats.storage?.archives?.size_gb?.toFixed(2) || 0} GB
								</div>
								<div class="mt-1 text-xs text-muted-foreground">Parquet cold storage</div>
							</div>
						</div>
					</CardContent>
				</Card>
			</TabsContent>
		</Tabs>

		<!-- Prometheus Info Footer -->
		<Card class="bg-muted/50">
			<CardContent class="py-4">
				<div class="flex items-center justify-between text-sm">
					<div class="text-muted-foreground">
						<span class="font-medium">Prometheus metrics:</span>
						<code class="ml-2 rounded bg-background px-2 py-1 text-xs"
							>{API_URL}/api/metrics</code
						>
					</div>
					<a
						href={`${API_URL}/api/metrics`}
						target="_blank"
						class="text-primary hover:underline"
					>
						View raw metrics
					</a>
				</div>
			</CardContent>
		</Card>
	{/if}
</div>
