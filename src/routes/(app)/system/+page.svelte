<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Activity, Cpu, HardDrive, MemoryStick, Video, Camera, Database, Zap } from '@lucide/svelte';
	import { Card, CardContent, CardHeader, CardTitle } from '$lib/components/ui/card';
	import { Badge } from '$lib/components/ui/badge';
	import { Tabs, TabsContent, TabsList, TabsTrigger } from '$lib/components/ui/tabs';
	
	// Frigate-style detailed camera stats
	interface CameraStat {
		id: string;
		name: string;
		is_active: boolean;
		input_fps: number;        // FPS from camera stream
		process_fps: number;      // FPS processed by detector
		detect_fps: number;       // FPS with detections (motion)
		skipped_fps: number;      // Frames skipped due to performance
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
			p50: number;  // 50th percentile
			p90: number;  // 90th percentile
			p99: number;  // 99th percentile
		};
		total_inferences: number;
		avg_detections: number;
		detector_type: string;  // 'CPU', 'GPU', 'Coral', etc.
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
			const res = await fetch('http://localhost:8000/api/system/stats');
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
		refreshInterval = setInterval(fetchStats, 2000);
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

<div class="container mx-auto p-6 space-y-6">
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">System</h1>
			<p class="text-muted-foreground mt-1">
				Monitor hardware usage and application performance
			</p>
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
					<span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
					<span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
				</span>
				Live
			</div>
		</div>
	</div>
	
	{#if !stats}
		<div class="flex items-center justify-center h-64">
			<div class="animate-pulse flex items-center gap-2 text-muted-foreground">
				<Activity class="h-5 w-5 animate-spin" />
				Loading system metrics...
			</div>
		</div>
	{:else}
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
			<Card>
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">CPU Usage</CardTitle>
					<Cpu class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					<div class="text-2xl font-bold">{stats.system.cpu_percent.toFixed(1)}%</div>
					<div class="mt-2 h-2 w-full rounded-full bg-secondary">
						<div 
							class="h-2 rounded-full transition-all duration-500 {getStatusColor(stats.system.cpu_percent)}"
							style="width: {stats.system.cpu_percent}%"
						></div>
					</div>
				</CardContent>
			</Card>
			
			<Card>
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">Memory</CardTitle>
					<MemoryStick class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					<div class="text-2xl font-bold">{stats.system.memory_percent.toFixed(1)}%</div>
					<p class="text-xs text-muted-foreground mt-1">
						{formatBytes(stats.system.memory_used_mb)} / {formatBytes(stats.system.memory_total_mb)}
					</p>
					<div class="mt-2 h-2 w-full rounded-full bg-secondary">
						<div 
							class="h-2 rounded-full transition-all duration-500 {getStatusColor(stats.system.memory_percent)}"
							style="width: {stats.system.memory_percent}%"
						></div>
					</div>
				</CardContent>
			</Card>
			
			<Card>
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">Storage</CardTitle>
					<HardDrive class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					{@const diskPercent = (stats.system.disk_used_gb / stats.system.disk_total_gb * 100)}
					<div class="text-2xl font-bold">{diskPercent.toFixed(1)}%</div>
					<p class="text-xs text-muted-foreground mt-1">
						{stats.system.disk_used_gb.toFixed(1)} GB / {stats.system.disk_total_gb.toFixed(0)} GB
					</p>
					<div class="mt-2 h-2 w-full rounded-full bg-secondary">
						<div 
							class="h-2 rounded-full transition-all duration-500 {getStatusColor(diskPercent)}"
							style="width: {diskPercent}%"
						></div>
					</div>
				</CardContent>
			</Card>
			
			<Card>
				<CardHeader class="flex flex-row items-center justify-between pb-2">
					<CardTitle class="text-sm font-medium">AI Detector</CardTitle>
					<Video class="h-4 w-4 text-muted-foreground" />
				</CardHeader>
				<CardContent>
					<div class="text-2xl font-bold">{stats.detector.avg_inference_ms.toFixed(1)}ms</div>
					<p class="text-xs text-muted-foreground mt-1">
						{stats.detector.model_name} - {stats.detector.total_inferences.toLocaleString()} inferences
					</p>
					<div class="mt-2 text-xs text-muted-foreground">
						<span class="inline-flex items-center gap-1">
							<span class="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
							{stats.detector.avg_detections.toFixed(1)} detections/frame
						</span>
					</div>
				</CardContent>
			</Card>
		</div>
		
		<Card>
			<CardHeader>
				<div class="flex items-center justify-between">
					<CardTitle>Cameras</CardTitle>
					<Badge variant="secondary">
						{stats.summary.active_cameras} active / {stats.summary.total_cameras} total
					</Badge>
				</div>
			</CardHeader>
			<CardContent>
				{#if stats.cameras.length === 0}
					<div class="text-center py-8 text-muted-foreground">
						<Video class="h-12 w-12 mx-auto mb-3 opacity-50" />
						<p>No cameras currently streaming</p>
						<p class="text-sm">Start a live stream to see camera metrics</p>
					</div>
				{:else}
					<div class="overflow-x-auto">
						<table class="w-full">
							<thead>
								<tr class="border-b text-left">
									<th class="pb-3 font-medium">Camera</th>
									<th class="pb-3 font-medium text-right">Status</th>
									<th class="pb-3 font-medium text-right">Input FPS</th>
									<th class="pb-3 font-medium text-right">Processed FPS</th>
									<th class="pb-3 font-medium text-right">Dropped</th>
									<th class="pb-3 font-medium text-right">Inference</th>
								</tr>
							</thead>
							<tbody class="text-sm">
								{#each stats.cameras as cam}
									<tr class="border-b last:border-0">
										<td class="py-3 font-medium">{cam.id}</td>
										<td class="py-3 text-right">
											{#if cam.is_active}
												<Badge variant="default" class="bg-emerald-500">Active</Badge>
											{:else}
												<Badge variant="secondary">Inactive</Badge>
											{/if}
										</td>
										<td class="py-3 text-right">{cam.input_fps.toFixed(1)}</td>
										<td class="py-3 text-right">{cam.processed_fps.toFixed(1)}</td>
										<td class="py-3 text-right">
											{#if cam.dropped_frames > 0}
												<span class="text-destructive font-medium">{cam.dropped_frames}</span>
											{:else}
												<span class="text-muted-foreground">0</span>
											{/if}
										</td>
										<td class="py-3 text-right">{cam.inference_ms.toFixed(1)}ms</td>
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			</CardContent>
		</Card>
		
		<Card class="bg-muted/50">
			<CardContent class="py-4">
				<div class="flex items-center justify-between text-sm">
					<div class="text-muted-foreground">
						<span class="font-medium">Prometheus metrics available at:</span>
						<code class="ml-2 bg-background px-2 py-1 rounded">/api/metrics</code>
					</div>
					<a 
						href="http://localhost:8000/api/metrics" 
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
