<script lang="ts">
	import { page } from '$app/stores';
	import { API_URL } from '$lib/api';
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import {
		ChevronLeft,
		Loader2,
		Download,
		FileJson,
		Activity,
		Shield,
		Clock,
		Eye,
		Users,
		AlertTriangle,
		Play,
		Pause,
		Maximize,
		Minimize,
		HardDrive,
		Layers,
		SkipBack,
		SkipForward,
		Settings,
		Trash2,
		MoreVertical,
		Check
	} from '@lucide/svelte';
	import { onMount, onDestroy } from 'svelte';

	let { data } = $props();

	let taskId = $derived(data.taskId);
	// Create a local state for task so we can update it immediately after rename
	let task = $state<any>(null);

	// Sync task with data.task when it changes
	$effect(() => {
		task = data.task;
	});

	let videoSrc = $state<string | null>(null);
	let status = $state<'loading' | 'processing' | 'ready' | 'error'>('loading');
	let pollInterval: NodeJS.Timeout;

	// Video element ref
	let videoEl = $state<HTMLVideoElement | null>(null);
	let isPlaying = $state(false);
	let isFullscreen = $state(false);
	let videoContainer: HTMLDivElement | null = $state(null);

	// Filtering
	let availableClasses = $state<string[]>([]);
	let activeClassFilter = $state<string>('all');

	// Timeline data
	let rawTimelineData = $state<
		{ timestamp: number; count: number; classes?: Record<string, number> }[]
	>([]);
	let timelineData = $derived(
		activeClassFilter === 'all'
			? rawTimelineData
			: rawTimelineData.map((d) => ({
					timestamp: d.timestamp,
					count: d.classes?.[activeClassFilter] || 0
				}))
	);

	let timelineCanvas = $state<HTMLCanvasElement | null>(null);
	let hoveredTime = $state<number | null>(null);
	let hoveredCount = $state<number | null>(null);
	let currentVideoTime = $state(0);
	let videoDuration = $state(0);
	let timelineLoaded = $state(false);

	// Controls visibility
	let showControls = $state(false);
	let controlsTimeout: ReturnType<typeof setTimeout> | null = null;

	// Initialize state based on loaded data
	$effect(() => {
		if (task) {
			if (task.status === 'completed') {
				status = 'ready';
				videoSrc = `${API_URL}/api/video/${taskId}/result`;
			} else if (task.status === 'failed') {
				status = 'error';
			} else {
				status = 'processing';
			}
			// Initialize task name for editing
			taskName = task.name || task.filename || `Task ${taskId?.slice(0, 8)}`;
		}
	});

	// Fetch timeline data when status is ready
	$effect(() => {
		if (status === 'ready' && !timelineLoaded) {
			fetchTimelineData();
		}
	});

	// Draw timeline when data or canvas changes
	$effect(() => {
		if (timelineCanvas && timelineData.length > 0) {
			drawTimeline();
		}
	});

	// Redraw on video time update to show playhead
	$effect(() => {
		if (timelineCanvas && timelineData.length > 0 && currentVideoTime >= 0) {
			drawTimeline();
		}
	});

	async function fetchTimelineData() {
		try {
			const res = await fetch(`${API_URL}/api/video/${taskId}/data`);
			if (!res.ok) return;
			const json = await res.json();
			if (json.frames && Array.isArray(json.frames)) {
				const classesFound = new Set<string>();

				rawTimelineData = json.frames.map((f: any) => {
					// Backend stores per-class counts in `class_frequencies` or similar depending on implementation
					// If missing, we'll gracefully fallback to just total count
					const classFreqs = f.class_frequencies || {};
					Object.keys(classFreqs).forEach((k) => classesFound.add(k));

					return {
						timestamp: f.timestamp,
						count: f.current_total_count ?? 0,
						classes: classFreqs
					};
				});

				availableClasses = Array.from(classesFound).sort();
				timelineLoaded = true;
			}
		} catch (e) {
			console.error('Failed to fetch timeline data', e);
		}
	}

	function drawTimeline() {
		if (!timelineCanvas) return;
		const canvas = timelineCanvas;
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		const rect = canvas.getBoundingClientRect();
		const dpr = window.devicePixelRatio || 1;
		canvas.width = rect.width * dpr;
		canvas.height = rect.height * dpr;
		ctx.scale(dpr, dpr);

		const w = rect.width;
		const h = rect.height;
		const padding = { top: 20, right: 16, bottom: 28, left: 40 };
		const chartW = w - padding.left - padding.right;
		const chartH = h - padding.top - padding.bottom;

		ctx.clearRect(0, 0, w, h);

		if (timelineData.length === 0) return;

		const maxCount = Math.max(...timelineData.map((d) => d.count), 1);
		const maxTime = timelineData[timelineData.length - 1].timestamp || 1;

		// Draw grid lines
		ctx.strokeStyle = 'rgba(255,255,255,0.06)';
		ctx.lineWidth = 1;
		const gridLines = 4;
		for (let i = 0; i <= gridLines; i++) {
			const y = padding.top + (chartH / gridLines) * i;
			ctx.beginPath();
			ctx.moveTo(padding.left, y);
			ctx.lineTo(w - padding.right, y);
			ctx.stroke();
		}

		// Y-axis labels
		ctx.fillStyle = 'rgba(255,255,255,0.4)';
		ctx.font = '10px system-ui, sans-serif';
		ctx.textAlign = 'right';
		ctx.textBaseline = 'middle';
		for (let i = 0; i <= gridLines; i++) {
			const val = Math.round(maxCount - (maxCount / gridLines) * i);
			const y = padding.top + (chartH / gridLines) * i;
			ctx.fillText(String(val), padding.left - 6, y);
		}

		// X-axis labels
		ctx.textAlign = 'center';
		ctx.textBaseline = 'top';
		const xLabels = 6;
		for (let i = 0; i <= xLabels; i++) {
			const t = (maxTime / xLabels) * i;
			const x = padding.left + (chartW / xLabels) * i;
			const mins = Math.floor(t / 60);
			const secs = Math.floor(t % 60);
			ctx.fillText(`${mins}:${secs.toString().padStart(2, '0')}`, x, h - padding.bottom + 8);
		}

		// Draw area fill
		const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + chartH);
		gradient.addColorStop(0, 'rgba(59, 130, 246, 0.35)');
		gradient.addColorStop(1, 'rgba(59, 130, 246, 0.02)');

		ctx.beginPath();
		ctx.moveTo(padding.left, padding.top + chartH);
		for (let i = 0; i < timelineData.length; i++) {
			const x = padding.left + (timelineData[i].timestamp / maxTime) * chartW;
			const y = padding.top + chartH - (timelineData[i].count / maxCount) * chartH;
			ctx.lineTo(x, y);
		}
		ctx.lineTo(
			padding.left + (timelineData[timelineData.length - 1].timestamp / maxTime) * chartW,
			padding.top + chartH
		);
		ctx.closePath();
		ctx.fillStyle = gradient;
		ctx.fill();

		// Draw line
		ctx.beginPath();
		ctx.strokeStyle = 'rgba(59, 130, 246, 0.9)';
		ctx.lineWidth = 2;
		ctx.lineJoin = 'round';
		for (let i = 0; i < timelineData.length; i++) {
			const x = padding.left + (timelineData[i].timestamp / maxTime) * chartW;
			const y = padding.top + chartH - (timelineData[i].count / maxCount) * chartH;
			if (i === 0) ctx.moveTo(x, y);
			else ctx.lineTo(x, y);
		}
		ctx.stroke();

		// Draw playhead
		if (videoDuration > 0) {
			const playX = padding.left + (currentVideoTime / maxTime) * chartW;
			if (playX >= padding.left && playX <= padding.left + chartW) {
				ctx.beginPath();
				ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
				ctx.lineWidth = 1.5;
				ctx.setLineDash([4, 3]);
				ctx.moveTo(playX, padding.top);
				ctx.lineTo(playX, padding.top + chartH);
				ctx.stroke();
				ctx.setLineDash([]);

				// Small triangle at top
				ctx.fillStyle = 'rgba(255,255,255,0.8)';
				ctx.beginPath();
				ctx.moveTo(playX - 4, padding.top);
				ctx.lineTo(playX + 4, padding.top);
				ctx.lineTo(playX, padding.top + 6);
				ctx.closePath();
				ctx.fill();
			}
		}

		// Draw hover indicator
		if (hoveredTime !== null) {
			const hoverX = padding.left + (hoveredTime / maxTime) * chartW;
			ctx.beginPath();
			ctx.strokeStyle = 'rgba(59, 130, 246, 0.6)';
			ctx.lineWidth = 1;
			ctx.setLineDash([2, 2]);
			ctx.moveTo(hoverX, padding.top);
			ctx.lineTo(hoverX, padding.top + chartH);
			ctx.stroke();
			ctx.setLineDash([]);

			if (hoveredCount !== null) {
				const dotY = padding.top + chartH - (hoveredCount / maxCount) * chartH;
				ctx.beginPath();
				ctx.arc(hoverX, dotY, 4, 0, Math.PI * 2);
				ctx.fillStyle = 'rgb(59, 130, 246)';
				ctx.fill();
				ctx.strokeStyle = 'white';
				ctx.lineWidth = 2;
				ctx.stroke();
			}
		}
	}

	function handleTimelineClick(e: MouseEvent) {
		if (!timelineCanvas || !videoEl || timelineData.length === 0) return;
		const rect = timelineCanvas.getBoundingClientRect();
		const padding = { left: 40, right: 16 };
		const chartW = rect.width - padding.left - padding.right;
		const x = e.clientX - rect.left - padding.left;
		if (x < 0 || x > chartW) return;

		const maxTime = timelineData[timelineData.length - 1].timestamp || 1;
		const targetTime = (x / chartW) * maxTime;
		videoEl.currentTime = targetTime;
	}

	function handleTimelineHover(e: MouseEvent) {
		if (!timelineCanvas || timelineData.length === 0) return;
		const rect = timelineCanvas.getBoundingClientRect();
		const padding = { left: 40, right: 16 };
		const chartW = rect.width - padding.left - padding.right;
		const x = e.clientX - rect.left - padding.left;
		if (x < 0 || x > chartW) {
			hoveredTime = null;
			hoveredCount = null;
			return;
		}

		const maxTime = timelineData[timelineData.length - 1].timestamp || 1;
		hoveredTime = (x / chartW) * maxTime;

		let nearest = timelineData[0];
		let minDist = Infinity;
		for (const d of timelineData) {
			const dist = Math.abs(d.timestamp - hoveredTime);
			if (dist < minDist) {
				minDist = dist;
				nearest = d;
			}
		}
		hoveredCount = nearest.count;
	}

	function handleTimelineLeave() {
		hoveredTime = null;
		hoveredCount = null;
	}

	function formatTime(seconds: number): string {
		const m = Math.floor(seconds / 60);
		const s = Math.floor(seconds % 60);
		return `${m}:${s.toString().padStart(2, '0')}`;
	}

	let taskProgress = $state(0);
	let isDeleteDialogOpen = $state(false);
	let isDeleting = $state(false);
	let isSettingsOpen = $state(false);
	let isSaving = $state(false);
	let taskName = $state('');

	async function deleteTask() {
		try {
			isDeleting = true;
			const res = await fetch(`${API_URL}/api/video/${taskId}`, {
				method: 'DELETE'
			});
			if (res.ok) {
				goto('/video-analytics');
			} else {
				const data = await res.json();
				alert(data.detail || 'Failed to delete task');
			}
		} catch (err) {
			console.error(err);
			alert('Error deleting task');
		} finally {
			isDeleting = false;
			isDeleteDialogOpen = false;
		}
	}

	async function saveSettings() {
		try {
			isSaving = true;
			const res = await fetch(`${API_URL}/api/video/${taskId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: taskName
				})
			});
			if (res.ok) {
				const responseData = await res.json();
				// Update the local task data with the new name
				task = { ...task, name: responseData.name || taskName };
				isSettingsOpen = false;
			} else {
				const data = await res.json();
				alert(data.detail || 'Failed to save settings');
			}
		} catch (err) {
			console.error(err);
			alert('Error saving settings');
		} finally {
			isSaving = false;
		}
	}

	async function checkStatus() {
		if (status === 'ready') return;
		try {
			const res = await fetch(`${API_URL}/api/video/${taskId}/status`);
			if (res.ok) {
				const data = await res.json();
				if (data.status === 'completed') {
					videoSrc = `${API_URL}/api/video/${taskId}/result`;
					status = 'ready';
					taskProgress = 100;
					stopPolling();
				} else if (data.status === 'failed') {
					status = 'error';
					stopPolling();
				} else if (data.status === 'processing') {
					status = 'processing';
					taskProgress = data.progress || 0;
				} else {
					status = 'processing';
				}
			}
		} catch (e) {
			console.error('Error checking status', e);
		}
	}

	function startPolling() {
		if (status === 'ready' || status === 'error') return;
		checkStatus();
		pollInterval = setInterval(checkStatus, 2000);
	}

	function stopPolling() {
		if (pollInterval) clearInterval(pollInterval);
	}

	// Video controls
	function handleVideoMouseMove() {
		showControls = true;
		if (controlsTimeout) clearTimeout(controlsTimeout);
		controlsTimeout = setTimeout(() => {
			showControls = false;
		}, 3000);
	}

	function handleVideoMouseLeave() {
		if (controlsTimeout) clearTimeout(controlsTimeout);
		controlsTimeout = setTimeout(() => {
			showControls = false;
		}, 1000);
	}

	function togglePlayPause() {
		if (!videoEl) return;
		if (videoEl.paused) {
			videoEl.play();
			isPlaying = true;
		} else {
			videoEl.pause();
			isPlaying = false;
		}
	}

	function seekToNextEvent() {
		if (!videoEl || timelineData.length === 0) return;

		// Find the next significant spike (count > 0) after current time + a small buffer
		const buffer = 1.0; // seconds
		const nextEvent = timelineData.find(
			(d) => d.timestamp > currentVideoTime + buffer && d.count > 0
		);

		if (nextEvent) {
			videoEl.currentTime = nextEvent.timestamp;
		} else {
			// No more events found, jump to end
			videoEl.currentTime = videoDuration;
		}
	}

	function seekToPrevEvent() {
		if (!videoEl || timelineData.length === 0) return;

		// Find the previous significant spike before current time - a small buffer
		const buffer = 2.0; // seconds backwards
		const reversedData = [...timelineData].reverse();
		const prevEvent = reversedData.find(
			(d) => d.timestamp < Math.max(0, currentVideoTime - buffer) && d.count > 0
		);

		if (prevEvent) {
			// Try to jump slightly before the spike context
			videoEl.currentTime = Math.max(0, prevEvent.timestamp - 1.0);
		} else {
			// No previous events found, jump to start
			videoEl.currentTime = 0;
		}
	}

	function toggleFullscreen() {
		if (!videoContainer) return;
		if (!document.fullscreenElement) {
			videoContainer.requestFullscreen().catch((e) => console.error(e));
		} else {
			document.exitFullscreen();
		}
	}

	function handleFullscreenChange() {
		isFullscreen = !!document.fullscreenElement;
	}

	onMount(() => {
		startPolling();
		document.addEventListener('fullscreenchange', handleFullscreenChange);
	});

	onDestroy(() => {
		stopPolling();
		if (controlsTimeout) clearTimeout(controlsTimeout);
		if (typeof document !== 'undefined') {
			document.removeEventListener('fullscreenchange', handleFullscreenChange);
		}
	});

	// Derived status helpers
	let statusLabel = $derived(
		status === 'loading'
			? 'Connecting'
			: status === 'processing'
				? 'Processing'
				: status === 'ready'
					? 'Completed'
					: 'Error'
	);
	let statusBadgeClass = $derived(
		status === 'ready'
			? 'bg-emerald-500/15 text-emerald-400'
			: status === 'processing' || status === 'loading'
				? 'bg-amber-500/15 text-amber-400'
				: 'bg-red-500/15 text-red-400'
	);
</script>

<svelte:head>
	<title>{task ? task.name || task.filename : 'Task Result'} · Locus</title>
</svelte:head>

<div class="flex h-full flex-col overflow-hidden">
	<!-- ─── Header Bar ─── -->
	<header
		class="flex shrink-0 items-center justify-between border-b bg-card/50 px-3 py-2 backdrop-blur-sm"
	>
		<div class="flex items-center gap-3">
			<Button variant="ghost" size="icon" href="/video-analytics" class="shrink-0">
				<ChevronLeft class="size-4" />
			</Button>
			<div class="flex flex-col">
				<div class="flex items-center gap-2">
					<h1 class="text-lg font-semibold tracking-tight">
						{task ? task.name || task.filename : `Task ${taskId?.slice(0, 8) ?? '—'}`}
					</h1>
					<!-- Status badge -->
					<span
						class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold tracking-wider uppercase {statusBadgeClass}"
					>
						{#if status === 'processing' || status === 'loading'}
							<span class="relative flex size-1.5">
								<span
									class="absolute inline-flex size-full animate-ping rounded-full bg-amber-400 opacity-75"
								></span>
								<span class="relative inline-flex size-1.5 rounded-full bg-amber-500"></span>
							</span>
						{:else if status === 'ready'}
							<span class="size-1.5 rounded-full bg-emerald-500"></span>
						{:else}
							<span class="size-1.5 rounded-full bg-red-500"></span>
						{/if}
						{statusLabel}
					</span>
				</div>
			</div>
		</div>
		<div class="flex items-center gap-2">
			{#if status === 'ready'}
				<Button
					variant="outline"
					size="sm"
					class="gap-1.5"
					href={`${API_URL}/api/video/${taskId}/data`}
					download
				>
					<FileJson class="size-3.5" />
					<span class="hidden sm:inline">Export JSON</span>
				</Button>
				<Button size="sm" class="gap-1.5" href={videoSrc} download>
					<Download class="size-3.5" />
					<span class="hidden sm:inline">Export Video</span>
				</Button>
			{/if}
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					<Button
						variant="ghost"
						size="icon"
						class="size-8 text-muted-foreground hover:text-foreground"
					>
						<Settings class="size-4" />
					</Button>
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end" class="w-48">
					<DropdownMenu.Label>Task Options</DropdownMenu.Label>
					<DropdownMenu.Separator />
					<DropdownMenu.Item onclick={() => (isSettingsOpen = true)}>
						<Settings class="mr-2 size-4" />
						Settings
					</DropdownMenu.Item>
					<DropdownMenu.Separator />
					<DropdownMenu.Item
						class="text-red-600 focus:bg-red-500/10 focus:text-red-600"
						onclick={() => (isDeleteDialogOpen = true)}
					>
						<Trash2 class="mr-2 size-4" />
						Delete Task
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</div>
	</header>

	{#if status === 'error'}
		<div
			class="mx-4 mt-3 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400"
		>
			<AlertTriangle class="size-4 shrink-0" />
			Failed to load video result. The analysis may have encountered an error.
		</div>
	{/if}

	<!-- ─── Main Content ─── -->
	<div class="flex min-h-0 flex-1 gap-3 overflow-hidden p-3 lg:flex-row">
		<!-- Left: Video + Timeline + Stats -->
		<div class="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
			<!-- Video Player -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				bind:this={videoContainer}
				class="group relative flex min-h-0 w-full flex-1 flex-col items-center justify-center overflow-hidden rounded-xl border border-border/50 bg-black shadow-xl"
				style={isFullscreen ? 'height: 100vh;' : ''}
				onmousemove={handleVideoMouseMove}
				onmouseleave={handleVideoMouseLeave}
			>
				{#if status === 'ready' && videoSrc}
					<!-- svelte-ignore a11y_media_has_caption -->
					<video
						bind:this={videoEl}
						src={videoSrc}
						class="size-full object-contain"
						controls
						autoplay
						loop
						playsinline
						crossorigin="anonymous"
						ontimeupdate={() => {
							if (videoEl) {
								currentVideoTime = videoEl.currentTime;
								isPlaying = !videoEl.paused;
							}
						}}
						onloadedmetadata={() => {
							if (videoEl) videoDuration = videoEl.duration;
						}}
						onplay={() => (isPlaying = true)}
						onpause={() => (isPlaying = false)}
					></video>

					<!-- HUD overlay - top left: filename -->
					<div class="pointer-events-none absolute top-3 left-3 z-10">
						<span class="font-mono text-[11px] font-medium tracking-wider text-white/50 uppercase">
							{task?.name || task?.filename || 'Video'}
						</span>
					</div>

					<!-- HUD overlay - top right: model -->
					<div class="pointer-events-none absolute top-3 right-3 z-10">
						<span class="font-mono text-[10px] text-white/40">
							{task?.model_name || 'yolo11n'} · {task?.fps}fps
						</span>
					</div>

					<!-- ─── Bottom Control Bar Overlay (shown on hover) ─── -->
					<div
						class="absolute right-0 bottom-0 left-0 z-20 flex items-center justify-between bg-gradient-to-t from-black/80 via-black/40 to-transparent px-4 pt-10 pb-3 transition-all duration-300 {showControls ||
						isFullscreen
							? 'translate-y-0 opacity-100'
							: 'translate-y-2 opacity-0'}"
					>
						<div class="flex items-center gap-3">
							<div class="flex items-center gap-1">
								<button
									onclick={seekToPrevEvent}
									class="flex items-center justify-center rounded-lg p-1.5 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
									title="Previous Event"
								>
									<SkipBack class="size-4" />
								</button>
								<button
									onclick={togglePlayPause}
									class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
								>
									{#if isPlaying}
										<Pause class="size-4" />
									{:else}
										<Play class="size-4" />
									{/if}
								</button>
								<button
									onclick={seekToNextEvent}
									class="flex items-center justify-center rounded-lg p-1.5 text-white/70 transition-colors hover:bg-white/10 hover:text-white"
									title="Next Event"
								>
									<SkipForward class="size-4" />
								</button>
							</div>
							<span class="font-mono text-xs text-white/60">
								{formatTime(currentVideoTime)} / {formatTime(videoDuration)}
							</span>
						</div>
						<div class="flex items-center gap-1">
							<button
								onclick={toggleFullscreen}
								class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
							>
								{#if isFullscreen}
									<Minimize class="size-4" />
								{:else}
									<Maximize class="size-4" />
								{/if}
							</button>
						</div>
					</div>
				{:else if status === 'processing' || status === 'loading'}
					<div
						class="absolute inset-0 flex size-full flex-col items-center justify-center gap-4 bg-gradient-to-br from-zinc-900 via-zinc-800 to-zinc-900"
					>
						<div class="relative">
							<Loader2 class="size-10 animate-spin text-blue-400" />
							{#if taskProgress > 0}
								<div class="absolute -bottom-6 left-1/2 -translate-x-1/2">
									<span class="font-mono text-lg font-bold text-white">{taskProgress}%</span>
								</div>
							{/if}
						</div>
						<div class="mt-4 flex flex-col items-center gap-2">
							<p class="text-sm font-medium text-white/70">Processing video analysis...</p>
							{#if taskProgress > 0}
								<div class="h-1.5 w-56 overflow-hidden rounded-full bg-white/10">
									<div
										class="h-full rounded-full bg-blue-500 transition-all duration-700 ease-out"
										style="width: {taskProgress}%"
									></div>
								</div>
							{/if}
							<p class="mt-1 text-xs text-white/40">
								This typically takes 10–30 seconds depending on video length.
							</p>
						</div>
					</div>
				{:else if status === 'error'}
					<div
						class="absolute inset-0 flex size-full flex-col items-center justify-center gap-3 bg-gradient-to-br from-zinc-900 via-zinc-800 to-zinc-900"
					>
						<AlertTriangle class="size-8 text-red-400/60" />
						<p class="text-sm text-white/50">Analysis failed</p>
					</div>
				{/if}
			</div>

			<!-- ─── Activity Timeline ─── -->
			{#if status === 'ready' && timelineData.length > 0}
				<div class="shrink-0 overflow-hidden rounded-lg border bg-card shadow-sm">
					<div class="flex items-center justify-between border-b px-3 py-1.5">
						<div class="flex items-center gap-2">
							<Activity class="size-3 text-blue-400" />
							<h3 class="text-[11px] font-semibold tracking-tight">Activity Timeline</h3>
						</div>
						<div class="flex items-center gap-3 text-[10px] text-muted-foreground">
							{#if hoveredTime !== null}
								<span class="font-mono text-blue-400">
									{formatTime(hoveredTime)} · {hoveredCount} objects
								</span>
							{:else}
								<span>Click to jump · Hover for details</span>
							{/if}
						</div>
					</div>

					<!-- ─── Filter Controls ─── -->
					{#if availableClasses.length > 0}
						<div class="flex items-center gap-1.5 overflow-x-auto border-b bg-muted/5 px-3 py-1">
							<button
								onclick={() => (activeClassFilter = 'all')}
								class="shrink-0 rounded-md px-2 py-0.5 text-[10px] font-medium transition-colors {activeClassFilter ===
								'all'
									? 'bg-primary text-primary-foreground'
									: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
							>
								All Objects
							</button>
							{#each availableClasses as cls}
								<button
									onclick={() => (activeClassFilter = cls)}
									class="shrink-0 rounded-md px-2 py-0.5 text-[10px] font-medium capitalize transition-colors {activeClassFilter ===
									cls
										? 'bg-primary text-primary-foreground'
										: 'text-muted-foreground hover:bg-muted hover:text-foreground'}"
								>
									{cls}
								</button>
							{/each}
						</div>
					{/if}

					<div class="px-2 py-1">
						<canvas
							bind:this={timelineCanvas}
							class="h-[80px] w-full cursor-crosshair rounded"
							onclick={handleTimelineClick}
							onmousemove={handleTimelineHover}
							onmouseleave={handleTimelineLeave}
							aria-label="Activity timeline chart - click to jump to time"
						></canvas>
					</div>
				</div>
			{/if}

			<!-- ─── Stats Strip ─── -->
			<div
				class="flex shrink-0 items-center gap-3 overflow-x-auto rounded-lg border bg-card/60 px-3 py-1.5 backdrop-blur-sm"
			>
				<div class="flex shrink-0 items-center gap-1.5">
					<Shield class="size-3 text-blue-400" />
					<span class="text-[11px] text-muted-foreground">Model</span>
					<span class="text-[11px] font-semibold">{task ? task.model_name || 'yolo11n' : '—'}</span>
				</div>
				<span class="text-border">│</span>
				<div class="flex shrink-0 items-center gap-1.5">
					<Clock class="size-3 text-purple-400" />
					<span class="text-[11px] font-semibold">{task ? task.duration || '--:--' : '--:--'}</span>
				</div>
				<span class="text-border">│</span>
				<div class="flex shrink-0 items-center gap-1.5">
					<HardDrive class="size-3 text-amber-400" />
					<span class="text-[11px] font-semibold">{task?.fps} FPS · ByteTrack</span>
				</div>
				<span class="text-border">│</span>
				<div class="flex shrink-0 items-center gap-1.5">
					<Layers class="size-3 text-emerald-400" />
					<span class="text-[11px] font-semibold capitalize">{statusLabel}</span>
				</div>
			</div>
		</div>

		<!-- ─── Right Sidebar: Detection Summary ─── -->
		<div class="hidden min-h-0 w-80 shrink-0 flex-col lg:flex xl:w-96">
			<div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
				<!-- Summary header -->
				<div class="border-b px-4 py-3">
					<div class="flex items-center gap-2">
						<Eye class="size-4 text-blue-400" />
						<h3 class="text-sm font-semibold tracking-tight">Detection Summary</h3>
					</div>
				</div>

				<div class="flex-1 overflow-y-auto p-4">
					{#if status === 'ready' && task}
						<!-- Total Count Hero -->
						<div class="mb-4 flex flex-col items-center rounded-xl border bg-muted/20 p-6">
							<div class="mb-1 text-xs font-medium tracking-wider text-muted-foreground uppercase">
								Total Unique Objects
							</div>
							<div class="text-5xl font-bold tracking-tight text-primary">
								{task.total_count || 0}
							</div>
							<div class="mt-2 flex items-center gap-1.5">
								<Users class="size-3.5 text-muted-foreground" />
								<span class="text-xs text-muted-foreground">tracked across entire video</span>
							</div>
						</div>

						<!-- Zone Counts -->
						{@const parsedZoneCounts = task.zone_counts ? JSON.parse(task.zone_counts) : null}
						{#if parsedZoneCounts && Object.keys(parsedZoneCounts).length > 0}
							<div class="mb-4">
								<h4
									class="mb-2 flex items-center gap-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase"
								>
									<Layers class="size-3.5" />
									Zone Breakdown
								</h4>
								<div class="space-y-2">
									{#each Object.entries(parsedZoneCounts) as [zoneId, count]}
										<div
											class="flex items-center justify-between rounded-lg border bg-muted/10 px-3 py-2.5"
										>
											<div class="flex items-center gap-2">
												<div class="size-2 rounded-full bg-blue-400"></div>
												<span class="truncate text-sm" title={zoneId}>
													{zoneId.length > 8 ? `Zone ${zoneId.slice(0, 4)}` : zoneId}
												</span>
											</div>
											<span class="font-mono text-lg font-bold">{count}</span>
										</div>
									{/each}
								</div>
							</div>
						{:else}
							<div class="mb-4 rounded-lg border border-dashed p-4 text-center">
								<p class="text-xs text-muted-foreground">No zones defined for this analysis.</p>
							</div>
						{/if}

						<!-- Analysis Context -->
						<div class="rounded-xl border bg-muted/10 p-4">
							<h4 class="mb-2 text-xs font-semibold tracking-wider text-muted-foreground uppercase">
								Analysis Context
							</h4>
							<p class="text-xs leading-relaxed text-muted-foreground">
								Processed using high-accuracy tracking at 12fps. Objects tracked via ByteTrack with
								unique ID assignment. Export raw JSON to view per-frame detections.
							</p>
						</div>
					{:else if status === 'processing' || status === 'loading'}
						<div class="flex flex-col items-center justify-center gap-3 py-12 text-center">
							<Loader2 class="size-6 animate-spin text-muted-foreground/50" />
							<p class="text-sm text-muted-foreground">Waiting for analysis to complete...</p>
							<p class="text-xs text-muted-foreground/60">Results will appear here automatically</p>
						</div>
					{:else}
						<div class="flex flex-col items-center justify-center gap-3 py-12 text-center">
							<AlertTriangle class="size-6 text-red-400/40" />
							<p class="text-sm text-muted-foreground">Analysis failed</p>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>

	<!-- ─── Footer ─── -->
	<footer
		class="flex shrink-0 items-center justify-between border-t bg-card/50 px-3 py-1.5 backdrop-blur-sm"
	>
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-1.5">
				<span
					class="size-1.5 rounded-full {status === 'ready'
						? 'bg-emerald-500'
						: status === 'error'
							? 'bg-red-500'
							: 'animate-pulse bg-amber-500'}"
				></span>
				<span class="text-[11px] text-muted-foreground">{statusLabel}</span>
			</div>
			{#if status === 'ready' && timelineData.length > 0}
				<div class="hidden items-center gap-1.5 sm:flex">
					<Activity class="size-3 text-muted-foreground" />
					<span class="text-[11px] text-muted-foreground">{timelineData.length} data points</span>
				</div>
			{/if}
		</div>
		<div class="flex items-center gap-4">
			<span class="text-[11px] text-muted-foreground">Task ID: {taskId?.slice(0, 8) ?? '—'}...</span
			>
		</div>
	</footer>
</div>

<!-- Settings Dialog -->
<Dialog.Root bind:open={isSettingsOpen}>
	<Dialog.Content class="sm:max-w-[425px]">
		<Dialog.Header>
			<Dialog.Title>Task Settings</Dialog.Title>
			<Dialog.Description>Update task name.</Dialog.Description>
		</Dialog.Header>

		<div class="grid gap-4 py-4">
			<div class="grid gap-2">
				<Label for="name">Task Name</Label>
				<Input id="name" bind:value={taskName} placeholder="e.g. My Analysis Task" />
			</div>
		</div>

		<Dialog.Footer class="gap-2 sm:justify-end">
			<Button variant="outline" onclick={() => (isSettingsOpen = false)}>Cancel</Button>
			<Button onclick={saveSettings} disabled={isSaving}>
				{#if isSaving}
					<Loader2 class="mr-2 size-4 animate-spin" />
					Saving...
				{:else}
					<Check class="mr-2 size-4" />
					Save Changes
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<!-- Delete Confirmation Dialog -->
<Dialog.Root bind:open={isDeleteDialogOpen}>
	<Dialog.Content class="sm:max-w-[400px]">
		<Dialog.Header>
			<Dialog.Title class="flex items-center gap-2 text-red-600">
				<AlertTriangle class="size-5" />
				Delete Task
			</Dialog.Title>
			<Dialog.Description>
				Are you sure you want to delete <strong
					>{task?.name || task?.filename || 'this task'}</strong
				>? This action cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer class="gap-2 sm:justify-end">
			<Button variant="outline" onclick={() => (isDeleteDialogOpen = false)}>Cancel</Button>
			<Button variant="destructive" onclick={deleteTask} disabled={isDeleting}>
				{#if isDeleting}
					<Loader2 class="mr-2 size-4 animate-spin" />
					Deleting...
				{:else}
					<Trash2 class="mr-2 size-4" />
					Delete Task
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
