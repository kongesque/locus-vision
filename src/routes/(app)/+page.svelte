<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { API_URL } from '$lib/api';
	import {
		Cpu,
		MemoryStick,
		HardDrive,
		Zap,
		Radio,
		ScanSearch,
		Activity,
		Video,
		Plus,
		Upload,
		ArrowRight,
		Clock,
		CircleDot,
		CheckCircle,
		Loader,
		AlertTriangle,
		Server
	} from '@lucide/svelte';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { goto } from '$app/navigation';
	import { addCameraDialogOpen } from '$lib/stores/add-camera-dialog.svelte';

	// ── Types ──────────────────────────────────────────────
	interface SystemStats {
		timestamp: number;
		system: {
			cpu_percent: number;
			memory_percent: number;
			memory_used_mb: number;
			memory_total_mb: number;
		};
		storage: {
			total: { used_gb: number; total_gb: number; percent: number };
			recordings: { size_gb: number; file_count: number };
			database: { size_mb: number };
			duckdb?: { size_mb: number };
		};
		detector: {
			model_name: string;
			inference_speed: { p50: number; p90: number; p99: number };
			total_inferences: number;
			avg_detections: number;
			detector_type: string;
		};
		cameras: {
			id: string;
			name: string;
			is_active: boolean;
			input_fps: number;
			process_fps: number;
			detect_fps: number;
			inference_ms: number;
		}[];
		summary: { active_cameras: number; total_cameras: number };
	}

	interface VideoTask {
		id: string;
		filename: string;
		status: string;
		progress: number;
		created_at: string;
		model_name?: string;
	}

	interface QueueStatus {
		pending: number;
		processing: { task_id: string; progress: number } | null;
		completed: number;
		failed: number;
	}

	// ── State ──────────────────────────────────────────────
	let stats = $state<SystemStats | null>(null);
	let videoTasks = $state<VideoTask[]>([]);
	let queueStatus = $state<QueueStatus | null>(null);
	let error = $state<string | null>(null);
	let refreshInterval: ReturnType<typeof setInterval> | null = null;

	// ── Derived ───────────────────────────────────────────
	let activeCameras = $derived(stats?.summary?.active_cameras ?? 0);
	let totalCameras = $derived(stats?.summary?.total_cameras ?? 0);
	let completedTasks = $derived(videoTasks.filter((t) => t.status === 'completed').length);
	let pendingTasks = $derived(
		videoTasks.filter((t) => t.status === 'pending' || t.status === 'processing').length
	);
	let recentTasks = $derived(videoTasks.slice(0, 6));

	// ── API Calls ─────────────────────────────────────────
	async function fetchAll() {
		try {
			const [sysRes, histRes, queueRes] = await Promise.allSettled([
				fetch(`${API_URL}/api/system/stats`),
				fetch('http://127.0.0.1:8000/api/video/history'),
				fetch('http://127.0.0.1:8000/api/video/queue/status')
			]);

			if (sysRes.status === 'fulfilled' && sysRes.value.ok) {
				stats = await sysRes.value.json();
			}
			if (histRes.status === 'fulfilled' && histRes.value.ok) {
				videoTasks = await histRes.value.json();
			}
			if (queueRes.status === 'fulfilled' && queueRes.value.ok) {
				queueStatus = await queueRes.value.json();
			}
			error = null;
		} catch (e) {
			error = 'Unable to connect to backend.';
		}
	}

	onMount(() => {
		fetchAll();
		refreshInterval = setInterval(fetchAll, 3000);
	});

	onDestroy(() => {
		if (refreshInterval) clearInterval(refreshInterval);
	});

	// ── Helpers ────────────────────────────────────────────
	function getStatusColor(percent: number): string {
		if (percent < 50) return 'bg-emerald-500';
		if (percent < 80) return 'bg-amber-500';
		return 'bg-red-500';
	}

	function getStatusGlow(percent: number): string {
		if (percent < 50) return 'shadow-emerald-500/20';
		if (percent < 80) return 'shadow-amber-500/20';
		return 'shadow-red-500/20';
	}

	function formatMb(mb: number): string {
		if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
		return `${Math.round(mb)} MB`;
	}

	function timeAgo(dateStr: string): string {
		const diff = Date.now() - new Date(dateStr).getTime();
		const mins = Math.floor(diff / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins}m ago`;
		const hrs = Math.floor(mins / 60);
		if (hrs < 24) return `${hrs}h ago`;
		return `${Math.floor(hrs / 24)}d ago`;
	}

	function taskStatusIcon(status: string) {
		if (status === 'completed') return CheckCircle;
		if (status === 'processing') return Loader;
		if (status === 'failed') return AlertTriangle;
		return CircleDot;
	}

	function taskStatusColor(status: string): string {
		if (status === 'completed') return 'text-emerald-500';
		if (status === 'processing') return 'text-blue-500 animate-spin';
		if (status === 'failed') return 'text-red-500';
		return 'text-muted-foreground';
	}

	function openAddCameraDialog() {
		addCameraDialogOpen.set(true);
		goto('/livestream');
	}
</script>

<svelte:head>
	<title>Dashboard · Locus</title>
</svelte:head>

<div class="relative flex flex-1 flex-col gap-4 p-4">
	<!-- ═══════════════════════════════════════════════════ -->
	<!-- HEADER                                             -->
	<!-- ═══════════════════════════════════════════════════ -->
	<div class="flex items-center justify-between">
		<div>
			<h1 class="text-3xl font-bold tracking-tight">Dashboard</h1>
			<p class="mt-1 text-muted-foreground">Edge analytics overview and system health</p>
		</div>
		<div class="flex items-center gap-3">
			{#if error}
				<Badge variant="destructive">{error}</Badge>
			{:else}
				<div class="flex items-center gap-2 text-sm text-muted-foreground">
					<span class="relative flex h-2 w-2">
						<span
							class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"
						></span>
						<span class="relative inline-flex h-2 w-2 rounded-full bg-emerald-500"></span>
					</span>
					Live
				</div>
			{/if}
		</div>
	</div>

	{#if !stats}
		<!-- Loading skeleton -->
		<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
			{#each Array(4) as _, i (i)}
				<div class="h-[120px] animate-pulse rounded-xl border bg-muted/30"></div>
			{/each}
		</div>
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
			<div class="h-[300px] animate-pulse rounded-xl border bg-muted/30 lg:col-span-2"></div>
			<div class="h-[300px] animate-pulse rounded-xl border bg-muted/30"></div>
		</div>
	{:else}
		<!-- ═══════════════════════════════════════════════════ -->
		<!-- TIER 1 : System Health                             -->
		<!-- ═══════════════════════════════════════════════════ -->
		<div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
			<!-- CPU -->
			<a href="/system" class="group">
				<Card.Root
					class="relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg {getStatusGlow(
						stats.system.cpu_percent
					)}"
				>
					<div
						class="absolute inset-x-0 bottom-0 h-1 transition-all duration-500 {getStatusColor(
							stats.system.cpu_percent
						)}"
						style="width: {stats.system.cpu_percent}%"
					></div>
					<Card.Header class="flex flex-row items-center justify-between pb-2">
						<Card.Title class="text-sm font-medium text-muted-foreground">CPU</Card.Title>
						<Cpu class="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
					</Card.Header>
					<Card.Content>
						<div class="text-3xl font-bold tracking-tight tabular-nums">
							{stats.system.cpu_percent.toFixed(1)}<span class="text-lg text-muted-foreground"
								>%</span
							>
						</div>
						<p class="mt-1 text-xs text-muted-foreground">Processor utilization</p>
					</Card.Content>
				</Card.Root>
			</a>

			<!-- Memory -->
			<a href="/system" class="group">
				<Card.Root
					class="relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg {getStatusGlow(
						stats.system.memory_percent
					)}"
				>
					<div
						class="absolute inset-x-0 bottom-0 h-1 transition-all duration-500 {getStatusColor(
							stats.system.memory_percent
						)}"
						style="width: {stats.system.memory_percent}%"
					></div>
					<Card.Header class="flex flex-row items-center justify-between pb-2">
						<Card.Title class="text-sm font-medium text-muted-foreground">Memory</Card.Title>
						<MemoryStick
							class="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary"
						/>
					</Card.Header>
					<Card.Content>
						<div class="text-3xl font-bold tracking-tight tabular-nums">
							{stats.system.memory_percent.toFixed(1)}<span class="text-lg text-muted-foreground"
								>%</span
							>
						</div>
						<p class="mt-1 text-xs text-muted-foreground">
							{formatMb(stats.system.memory_used_mb)} / {formatMb(stats.system.memory_total_mb)}
						</p>
					</Card.Content>
				</Card.Root>
			</a>

			<!-- Storage -->
			<a href="/system" class="group">
				<Card.Root
					class="relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg {getStatusGlow(
						stats.storage?.total?.percent || 0
					)}"
				>
					<div
						class="absolute inset-x-0 bottom-0 h-1 transition-all duration-500 {getStatusColor(
							stats.storage?.total?.percent || 0
						)}"
						style="width: {stats.storage?.total?.percent || 0}%"
					></div>
					<Card.Header class="flex flex-row items-center justify-between pb-2">
						<Card.Title class="text-sm font-medium text-muted-foreground">Storage</Card.Title>
						<HardDrive
							class="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary"
						/>
					</Card.Header>
					<Card.Content>
						<div class="text-3xl font-bold tracking-tight tabular-nums">
							{(stats.storage?.total?.percent || 0).toFixed(0)}<span
								class="text-lg text-muted-foreground">%</span
							>
						</div>
						<p class="mt-1 text-xs text-muted-foreground">
							{stats.storage?.total?.used_gb?.toFixed(1) || 0} / {stats.storage?.total?.total_gb?.toFixed(
								0
							) || 0} GB
						</p>
					</Card.Content>
				</Card.Root>
			</a>

			<!-- Detector / Inference -->
			<a href="/system" class="group">
				<Card.Root
					class="relative overflow-hidden transition-all duration-300 hover:scale-[1.02] hover:shadow-lg"
				>
					<div
						class="absolute inset-x-0 bottom-0 h-1 bg-primary/60 transition-all duration-500"
						style="width: {Math.min((stats.detector?.inference_speed?.p50 || 0) / 2, 100)}%"
					></div>
					<Card.Header class="flex flex-row items-center justify-between pb-2">
						<Card.Title class="text-sm font-medium text-muted-foreground">Inference</Card.Title>
						<Zap class="h-4 w-4 text-muted-foreground transition-colors group-hover:text-primary" />
					</Card.Header>
					<Card.Content>
						{#if stats.detector?.inference_speed}
							<div class="text-3xl font-bold tracking-tight tabular-nums">
								{(stats.detector.inference_speed.p50 || 0).toFixed(0)}<span
									class="text-lg text-muted-foreground">ms</span
								>
							</div>
							<p class="mt-1 text-xs text-muted-foreground">
								{stats.detector.model_name || 'yolo11n'} · p50
							</p>
						{:else}
							<div class="text-3xl font-bold tracking-tight tabular-nums">
								—<span class="text-lg text-muted-foreground">ms</span>
							</div>
							<p class="mt-1 text-xs text-muted-foreground">No detector data</p>
						{/if}
					</Card.Content>
				</Card.Root>
			</a>
		</div>

		<!-- ═══════════════════════════════════════════════════ -->
		<!-- TIER 2 : Streams, Jobs & Quick Actions             -->
		<!-- ═══════════════════════════════════════════════════ -->
		<div class="grid grid-cols-1 gap-4 lg:grid-cols-3">
			<!-- Live Cameras Card -->
			<a href="/livestream" class="group">
				<Card.Root
					class="flex h-full flex-col transition-all duration-300 hover:scale-[1.01] hover:shadow-lg"
				>
					<Card.Header class="flex flex-row items-center justify-between pb-3">
						<div class="flex items-center gap-2">
							<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10">
								<Radio class="h-4 w-4 text-emerald-500" />
							</div>
							<Card.Title class="text-sm font-medium">Live Cameras</Card.Title>
						</div>
						<ArrowRight
							class="h-4 w-4 text-muted-foreground opacity-0 transition-all group-hover:opacity-100"
						/>
					</Card.Header>
					<Card.Content class="flex flex-1 flex-col justify-between">
						<div>
							<div class="flex items-baseline gap-2">
								<span class="text-4xl font-bold tracking-tight tabular-nums">{activeCameras}</span>
								<span class="text-sm text-muted-foreground">/ {totalCameras}</span>
							</div>
							<p class="mt-1 text-xs text-muted-foreground">streams actively running</p>
						</div>

						{#if stats.cameras && stats.cameras.length > 0}
							<div class="mt-4 space-y-2">
								{#each stats.cameras.slice(0, 3) as cam (cam.id)}
									<div
										class="flex items-center justify-between rounded-md bg-muted/50 px-3 py-1.5 text-xs"
									>
										<div class="flex items-center gap-2">
											<span
												class="h-1.5 w-1.5 rounded-full {cam.is_active
													? 'bg-emerald-500'
													: 'bg-zinc-400'}"
											></span>
											<span class="truncate font-medium">{cam.name || cam.id.slice(0, 8)}</span>
										</div>
										<span class="text-muted-foreground tabular-nums"
											>{cam.detect_fps?.toFixed(1) || '0'} fps</span
										>
									</div>
								{/each}
							</div>
						{/if}
					</Card.Content>
				</Card.Root>
			</a>

			<!-- Video Analytics Queue Card -->
			<a href="/video-analytics" class="group">
				<Card.Root
					class="flex h-full flex-col transition-all duration-300 hover:scale-[1.01] hover:shadow-lg"
				>
					<Card.Header class="flex flex-row items-center justify-between pb-3">
						<div class="flex items-center gap-2">
							<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-500/10">
								<ScanSearch class="h-4 w-4 text-blue-500" />
							</div>
							<Card.Title class="text-sm font-medium">Video Analytics</Card.Title>
						</div>
						<ArrowRight
							class="h-4 w-4 text-muted-foreground opacity-0 transition-all group-hover:opacity-100"
						/>
					</Card.Header>
					<Card.Content class="flex flex-1 flex-col justify-between">
						<div class="grid grid-cols-3 gap-3">
							<div class="rounded-lg bg-muted/50 p-3 text-center">
								<div class="text-2xl font-bold tabular-nums">{completedTasks}</div>
								<p class="mt-0.5 text-[10px] text-muted-foreground">Completed</p>
							</div>
							<div class="rounded-lg bg-muted/50 p-3 text-center">
								<div class="text-2xl font-bold tabular-nums">{pendingTasks}</div>
								<p class="mt-0.5 text-[10px] text-muted-foreground">In Queue</p>
							</div>
							<div class="rounded-lg bg-muted/50 p-3 text-center">
								<div class="text-2xl font-bold tabular-nums">{videoTasks.length}</div>
								<p class="mt-0.5 text-[10px] text-muted-foreground">Total Jobs</p>
							</div>
						</div>

						{#if queueStatus?.processing}
							<div
								class="mt-4 flex items-center gap-2 rounded-md border border-blue-500/20 bg-blue-500/5 px-3 py-2 text-xs"
							>
								<Loader class="h-3 w-3 animate-spin text-blue-500" />
								<span class="text-muted-foreground">Processing</span>
								<div class="ml-auto h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
									<div
										class="h-full rounded-full bg-blue-500 transition-all duration-500"
										style="width: {queueStatus.processing.progress}%"
									></div>
								</div>
								<span class="font-medium tabular-nums">{queueStatus.processing.progress}%</span>
							</div>
						{/if}
					</Card.Content>
				</Card.Root>
			</a>

			<!-- Quick Actions Card -->
			<Card.Root class="flex h-full flex-col">
				<Card.Header class="pb-3">
					<div class="flex items-center gap-2">
						<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
							<Zap class="h-4 w-4 text-primary" />
						</div>
						<Card.Title class="text-sm font-medium">Quick Actions</Card.Title>
					</div>
				</Card.Header>
				<Card.Content class="flex flex-1 flex-col gap-2">
					<Button variant="outline" class="w-full justify-start gap-2" onclick={openAddCameraDialog}>
						<Plus class="h-4 w-4" />
						New Camera Stream
					</Button>
					<a href="/video-analytics" class="w-full">
						<Button variant="outline" class="w-full justify-start gap-2">
							<Upload class="h-4 w-4" />
							Upload Video
						</Button>
					</a>
					<a href="/analytics" class="w-full">
						<Button variant="outline" class="w-full justify-start gap-2">
							<Activity class="h-4 w-4" />
							View Historical Analytics
						</Button>
					</a>
					<a href="/system" class="w-full">
						<Button variant="outline" class="w-full justify-start gap-2">
							<Server class="h-4 w-4" />
							System Monitor
						</Button>
					</a>
				</Card.Content>
			</Card.Root>
		</div>

		<!-- ═══════════════════════════════════════════════════ -->
		<!-- TIER 3 : Recent Activity                           -->
		<!-- ═══════════════════════════════════════════════════ -->
		<Card.Root>
			<Card.Header class="flex flex-row items-center justify-between">
				<div class="flex items-center gap-2">
					<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-500/10">
						<Clock class="h-4 w-4 text-purple-500" />
					</div>
					<div>
						<Card.Title class="text-sm font-medium">Recent Activity</Card.Title>
						<Card.Description class="text-xs">Latest video analytics jobs</Card.Description>
					</div>
				</div>
				<a href="/video-analytics">
					<Button variant="ghost" size="sm" class="gap-1 text-xs text-muted-foreground">
						View all
						<ArrowRight class="h-3 w-3" />
					</Button>
				</a>
			</Card.Header>
			<Card.Content>
				{#if recentTasks.length > 0}
					<div class="space-y-1">
						{#each recentTasks as task}
							{@const StatusIcon = taskStatusIcon(task.status)}
							<a
								href="/video-analytics/{task.id}"
								class="group flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-muted/50"
							>
								<StatusIcon class="h-4 w-4 shrink-0 {taskStatusColor(task.status)}" />
								<div class="flex min-w-0 flex-1 items-center justify-between gap-2">
									<div class="min-w-0">
										<p class="truncate text-sm font-medium">{task.filename || task.id}</p>
										<p class="text-xs text-muted-foreground">
											{task.model_name || 'yolo11n'} · {timeAgo(task.created_at)}
										</p>
									</div>
									<div class="flex shrink-0 items-center gap-2">
										{#if task.status === 'processing' && task.progress > 0}
											<div class="h-1.5 w-12 overflow-hidden rounded-full bg-secondary">
												<div
													class="h-full rounded-full bg-blue-500 transition-all"
													style="width: {task.progress}%"
												></div>
											</div>
										{/if}
										<Badge
											variant={task.status === 'completed'
												? 'default'
												: task.status === 'failed'
													? 'destructive'
													: 'secondary'}
											class="text-[10px]"
										>
											{task.status}
										</Badge>
									</div>
								</div>
							</a>
						{/each}
					</div>
				{:else}
					<div class="flex flex-col items-center justify-center py-8 text-center">
						<Video class="mb-3 h-10 w-10 text-muted-foreground/30" />
						<p class="text-sm text-muted-foreground">No activity yet</p>
						<p class="mt-1 text-xs text-muted-foreground">
							Start a live stream or upload a video to see activity here
						</p>
					</div>
				{/if}
			</Card.Content>
		</Card.Root>
	{/if}
</div>
