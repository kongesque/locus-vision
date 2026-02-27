<script lang="ts">
	import { page } from '$app/stores';
	import { Button } from '$lib/components/ui/button/index.js';
	import {
		ChevronLeft,
		Maximize,
		Minimize,
		Camera,
		Circle,
		Volume2,
		VolumeOff,
		Settings,
		Shield,
		Video,
		Wifi,
		WifiOff,
		HardDrive,
		Clock,
		Eye,
		Users,
		Car,
		Activity,
		AlertTriangle,
		Crosshair,
		ZoomIn,
		ZoomOut,
		ChevronUp,
		ChevronDown,
		MoveLeft,
		MoveRight,
		RotateCcw,
		ImageIcon
	} from '@lucide/svelte';
	import { onMount, onDestroy } from 'svelte';

	const taskId = $derived($page.params.taskId);

	// ─── Camera State ───
	let cameraName = $state('Front Entrance');
	let cameraStatus = $state<'live' | 'connecting' | 'offline' | 'error'>('live');
	let cameraType = $state<'webcam' | 'rtsp'>('rtsp');
	let cameraUrl = $state('rtsp://192.168.1.64:554/stream1');
	let modelName = $state('YOLOv11n');
	let resolution = $state('1920×1080');
	let fps = $state(24);
	let bitrate = $state('4.2 Mbps');
	let errorMsg = $state<string | null>(null);
	let uptime = $state('02:34:17');

	// ─── Detection State ───
	let zones = $state<any[]>([
		{ id: 'zone-entrance', color: '#3b82f6', name: 'Entrance', points: [] },
		{ id: 'zone-parking', color: '#f59e0b', name: 'Parking Lot', points: [] },
		{ id: 'zone-lobby', color: '#10b981', name: 'Main Lobby', points: [] }
	]);
	let trackCount = $state(12);
	let zoneCounts = $state<Record<string, number>>({
		'zone-entrance': 5,
		'zone-parking': 3,
		'zone-lobby': 4
	});

	// ─── UI State ───
	let isFullscreen = $state(false);
	let isMuted = $state(true);
	let isRecording = $state(true);
	let showPTZ = $state(false);
	let showControls = $state(false);
	let controlsTimeout: ReturnType<typeof setTimeout> | null = null;
	let videoContainer: HTMLDivElement | null = $state(null);
	let activeEventFilter = $state<string>('all');

	// ─── Activity Log ───
	type EventType = 'person' | 'vehicle' | 'motion' | 'zone' | 'alert';
	interface ActivityEvent {
		id: string;
		time: string;
		message: string;
		type: EventType;
		zone?: string;
	}

	const eventTypeConfig: Record<EventType, { label: string; color: string; bgColor: string }> = {
		person: { label: 'Person', color: 'text-blue-400', bgColor: 'bg-blue-500/15' },
		vehicle: { label: 'Vehicle', color: 'text-amber-400', bgColor: 'bg-amber-500/15' },
		motion: { label: 'Motion', color: 'text-emerald-400', bgColor: 'bg-emerald-500/15' },
		zone: { label: 'Zone Entry', color: 'text-purple-400', bgColor: 'bg-purple-500/15' },
		alert: { label: 'Alert', color: 'text-red-400', bgColor: 'bg-red-500/15' }
	};

	let activityLogs = $state<ActivityEvent[]>([]);

	function addActivityLog(message: string, type: EventType, zone?: string) {
		const now = new Date();
		const timeStr = now.toLocaleTimeString([], {
			hour12: false,
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});
		activityLogs = [
			{ time: timeStr, message, type, zone, id: crypto.randomUUID() },
			...activityLogs
		].slice(0, 100);
	}

	let filteredLogs = $derived(
		activeEventFilter === 'all'
			? activityLogs
			: activityLogs.filter((l) => l.type === activeEventFilter)
	);

	// ─── Mock Event Generator ───
	let mockInterval: ReturnType<typeof setInterval> | null = null;
	const mockEvents: { msg: string; type: EventType; zone?: string }[] = [
		{ msg: 'Person detected near entrance', type: 'person', zone: 'Entrance' },
		{ msg: 'Vehicle entering parking lot', type: 'vehicle', zone: 'Parking Lot' },
		{ msg: 'Motion detected in sector B', type: 'motion' },
		{ msg: 'Person entered Main Lobby zone', type: 'zone', zone: 'Main Lobby' },
		{ msg: 'Person detected at entrance', type: 'person', zone: 'Entrance' },
		{ msg: 'Vehicle stopped in parking zone', type: 'vehicle', zone: 'Parking Lot' },
		{ msg: 'Loitering alert — Entrance zone', type: 'alert', zone: 'Entrance' },
		{ msg: 'Person crossed line A→B', type: 'zone' },
		{ msg: 'Motion spike detected', type: 'motion' },
		{ msg: 'New person tracked (ID #47)', type: 'person' }
	];

	function startMockEvents() {
		// Seed initial events
		for (let i = 0; i < 6; i++) {
			const ev = mockEvents[Math.floor(Math.random() * mockEvents.length)];
			addActivityLog(ev.msg, ev.type, ev.zone);
		}
		// Continue adding
		mockInterval = setInterval(
			() => {
				const ev = mockEvents[Math.floor(Math.random() * mockEvents.length)];
				addActivityLog(ev.msg, ev.type, ev.zone);
				// Vary counts slightly
				trackCount = Math.max(0, trackCount + Math.floor(Math.random() * 3) - 1);
				zoneCounts = {
					'zone-entrance': Math.max(
						0,
						(zoneCounts['zone-entrance'] || 0) + Math.floor(Math.random() * 3) - 1
					),
					'zone-parking': Math.max(
						0,
						(zoneCounts['zone-parking'] || 0) + Math.floor(Math.random() * 3) - 1
					),
					'zone-lobby': Math.max(
						0,
						(zoneCounts['zone-lobby'] || 0) + Math.floor(Math.random() * 3) - 1
					)
				};
			},
			3500 + Math.random() * 2000
		);
	}

	// ─── Timestamp ticker for HUD ───
	let currentTime = $state(new Date());
	let clockInterval: ReturnType<typeof setInterval> | null = null;

	// ─── Controls visibility ───
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
			showPTZ = false;
		}, 1000);
	}

	// ─── Fullscreen ───
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

	// ─── TODO: Backend stubs ───
	function handleSnapshot() {
		// TODO: Call backend API to capture a snapshot from the camera
		// POST /api/cameras/{taskId}/snapshot
		console.log('TODO: Snapshot captured');
	}

	function handleRecordToggle() {
		// TODO: Call backend API to toggle recording
		// POST /api/cameras/{taskId}/record
		isRecording = !isRecording;
	}

	function handleMuteToggle() {
		// TODO: Toggle audio stream from the camera
		isMuted = !isMuted;
	}

	function handlePTZ(direction: string) {
		// TODO: Send PTZ command to backend
		// POST /api/cameras/{taskId}/ptz { action: direction }
		console.log('TODO: PTZ command:', direction);
	}

	// ─── Lifecycle ───
	onMount(() => {
		// TODO: Fetch camera info from backend API
		// GET /api/cameras/{taskId}
		// Response: { name, type, url, model, status, zones, ... }

		// TODO: Connect to video stream (RTSP/WebRTC/MJPEG)
		// The backend MJPEG proxy was removed. Reconnect when backend is ready.

		// TODO: WebSocket for real-time analytics
		// ws://localhost:8000/api/cameras/{taskId}/ws

		startMockEvents();
		clockInterval = setInterval(() => {
			currentTime = new Date();
		}, 1000);
		document.addEventListener('fullscreenchange', handleFullscreenChange);
	});

	onDestroy(() => {
		if (mockInterval) clearInterval(mockInterval);
		if (clockInterval) clearInterval(clockInterval);
		if (controlsTimeout) clearTimeout(controlsTimeout);
		if (typeof document !== 'undefined') {
			document.removeEventListener('fullscreenchange', handleFullscreenChange);
		}
	});

	// ─── Formatted time for HUD ───
	let hudTime = $derived(
		currentTime.toLocaleTimeString([], {
			hour12: false,
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		})
	);
	let hudDate = $derived(
		currentTime.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' })
	);

	// ─── Connection quality (mock) ───
	let signalStrength = $state<'excellent' | 'good' | 'poor'>('excellent');
	const signalColors = {
		excellent: 'text-emerald-400',
		good: 'text-amber-400',
		poor: 'text-red-400'
	};
</script>

<svelte:head>
	<title>{cameraName} · Live · Locus</title>
</svelte:head>

<div class="flex flex-1 flex-col overflow-hidden">
	<!-- ─── Header Bar ─── -->
	<header class="flex items-center justify-between border-b bg-card/50 px-4 py-3 backdrop-blur-sm">
		<div class="flex items-center gap-3">
			<Button variant="ghost" size="icon" href="/livestream" class="shrink-0">
				<ChevronLeft class="size-4" />
			</Button>
			<div class="flex flex-col">
				<div class="flex items-center gap-2">
					<h1 class="text-lg font-semibold tracking-tight">{cameraName}</h1>
					<!-- Live badge -->
					{#if cameraStatus === 'live'}
						<span
							class="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-bold tracking-wider text-red-400 uppercase"
						>
							<span class="relative flex size-1.5">
								<span
									class="absolute inline-flex size-full animate-ping rounded-full bg-red-400 opacity-75"
								></span>
								<span class="relative inline-flex size-1.5 rounded-full bg-red-500"></span>
							</span>
							Live
						</span>
					{:else if cameraStatus === 'connecting'}
						<span
							class="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-bold tracking-wider text-amber-400 uppercase"
						>
							Connecting
						</span>
					{:else}
						<span
							class="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2 py-0.5 text-[11px] font-bold tracking-wider text-red-400 uppercase"
						>
							Offline
						</span>
					{/if}
				</div>
				<p class="text-xs text-muted-foreground">
					{cameraType === 'rtsp' ? cameraUrl : 'Local Webcam'} · {resolution}
				</p>
			</div>
		</div>
		<div class="flex items-center gap-2">
			<!-- Signal indicator -->
			<div class="flex items-center gap-1.5 rounded-lg border bg-card px-2.5 py-1.5">
				{#if cameraStatus === 'live'}
					<Wifi class="size-3.5 {signalColors[signalStrength]}" />
				{:else}
					<WifiOff class="size-3.5 text-red-400" />
				{/if}
				<span class="text-xs font-medium text-muted-foreground capitalize">{signalStrength}</span>
			</div>
			<!-- Recording indicator -->
			{#if isRecording}
				<div
					class="flex items-center gap-1.5 rounded-lg border border-red-500/20 bg-red-500/10 px-2.5 py-1.5"
				>
					<Circle class="size-3 animate-pulse fill-red-500 text-red-500" />
					<span class="text-xs font-medium text-red-400">REC</span>
				</div>
			{/if}
			<Button
				variant="ghost"
				size="icon"
				class="size-8"
				onclick={() => console.log('TODO: Camera settings')}
			>
				<Settings class="size-4" />
			</Button>
		</div>
	</header>

	{#if errorMsg}
		<div
			class="mx-4 mt-3 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-400"
		>
			<AlertTriangle class="size-4 shrink-0" />
			{errorMsg}
		</div>
	{/if}

	<!-- ─── Main Content ─── -->
	<div class="flex flex-1 flex-col gap-4 overflow-y-auto p-4 lg:flex-row">
		<!-- Left: Video + Stats -->
		<div class="flex min-w-0 flex-1 flex-col gap-4">
			<!-- Video Player -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				bind:this={videoContainer}
				class="group relative flex w-full flex-col items-center justify-center overflow-hidden rounded-xl border border-border/50 bg-black shadow-xl"
				style={isFullscreen ? 'height: 100vh;' : 'height: calc(100vh - 18rem); min-height: 24rem;'}
				onmousemove={handleVideoMouseMove}
				onmouseleave={handleVideoMouseLeave}
			>
				<!-- TODO: Connect to actual video stream -->
				<!-- Placeholder: dark gradient simulating a camera feed -->
				<div class="absolute inset-0 bg-gradient-to-br from-zinc-900 via-zinc-800 to-zinc-900">
					<div class="absolute inset-0 bg-[url('/locus.png')] bg-cover bg-center opacity-30"></div>
					<!-- Scanline effect -->
					<div
						class="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(0,0,0,0.03)_2px,rgba(0,0,0,0.03)_4px)]"
					></div>
				</div>

				<!-- Canvas overlay for detection boxes -->
				<canvas class="pointer-events-none absolute inset-0 size-full"></canvas>

				<!-- ─── HUD Overlay (always visible) ─── -->
				<!-- Top left: Camera info -->
				<div class="pointer-events-none absolute top-3 left-3 z-10 flex flex-col gap-1">
					<div class="flex items-center gap-2">
						<span class="font-mono text-[11px] font-medium tracking-wider text-white/60 uppercase">
							{cameraName}
						</span>
					</div>
					<span class="font-mono text-[10px] text-white/40">
						{hudDate}
						{hudTime}
					</span>
				</div>

				<!-- Top right: recording dot -->
				{#if isRecording}
					<div class="absolute top-3 right-3 z-10 flex items-center gap-1.5">
						<span class="size-2 animate-pulse rounded-full bg-red-500"></span>
						<span class="font-mono text-[10px] font-bold text-red-400/80">REC</span>
					</div>
				{/if}

				<!-- Bottom left: model + FPS -->
				<div class="absolute bottom-3 left-3 z-10">
					<span class="font-mono text-[10px] text-white/40">
						{modelName} · {fps}fps · {resolution}
					</span>
				</div>

				<!-- ─── PTZ Controls (top-right, shown on hover) ─── -->
				<div
					class="absolute top-12 right-3 z-20 transition-all duration-300"
					class:opacity-0={!showPTZ}
					class:pointer-events-none={!showPTZ}
					class:opacity-100={showPTZ}
				>
					<div
						class="flex flex-col items-center gap-1 rounded-xl border border-white/10 bg-black/70 p-2 backdrop-blur-md"
					>
						<button
							onclick={() => handlePTZ('up')}
							class="flex size-8 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
						>
							<ChevronUp class="size-4" />
						</button>
						<div class="flex items-center gap-1">
							<button
								onclick={() => handlePTZ('left')}
								class="flex size-8 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
							>
								<MoveLeft class="size-4" />
							</button>
							<button
								onclick={() => handlePTZ('home')}
								class="flex size-7 items-center justify-center rounded-full border border-white/20 text-white/50 transition-colors hover:bg-white/10 hover:text-white"
							>
								<RotateCcw class="size-3" />
							</button>
							<button
								onclick={() => handlePTZ('right')}
								class="flex size-8 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
							>
								<MoveRight class="size-4" />
							</button>
						</div>
						<button
							onclick={() => handlePTZ('down')}
							class="flex size-8 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
						>
							<ChevronDown class="size-4" />
						</button>
						<div class="mt-1 flex items-center gap-1 border-t border-white/10 pt-2">
							<button
								onclick={() => handlePTZ('zoom-out')}
								class="flex size-7 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
							>
								<ZoomOut class="size-3.5" />
							</button>
							<button
								onclick={() => handlePTZ('zoom-in')}
								class="flex size-7 items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/10 hover:text-white"
							>
								<ZoomIn class="size-3.5" />
							</button>
						</div>
					</div>
				</div>

				<!-- ─── Bottom Control Bar (shown on hover) ─── -->
				<div
					class="absolute right-0 bottom-0 left-0 z-20 flex items-center justify-between bg-gradient-to-t from-black/80 via-black/40 to-transparent px-4 pt-10 pb-3 transition-all duration-300"
					class:opacity-0={!showControls && !isFullscreen}
					class:translate-y-2={!showControls && !isFullscreen}
					class:opacity-100={showControls || isFullscreen}
					class:translate-y-0={showControls || isFullscreen}
				>
					<div class="flex items-center gap-1">
						<button
							onclick={handleSnapshot}
							class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
							title="Capture Snapshot"
						>
							<Camera class="size-4" />
							<span class="hidden sm:inline">Snapshot</span>
						</button>
						<button
							onclick={handleRecordToggle}
							class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-white/10 {isRecording
								? 'text-red-400'
								: 'text-white/80'}"
							title={isRecording ? 'Stop Recording' : 'Start Recording'}
						>
							{#if isRecording}
								<Circle class="size-4 fill-red-500" />
							{:else}
								<Video class="size-4" />
							{/if}
							<span class="hidden sm:inline">{isRecording ? 'Recording' : 'Record'}</span>
						</button>
						<button
							onclick={handleMuteToggle}
							class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
							title={isMuted ? 'Unmute' : 'Mute'}
						>
							{#if isMuted}
								<VolumeOff class="size-4" />
							{:else}
								<Volume2 class="size-4" />
							{/if}
						</button>
					</div>
					<div class="flex items-center gap-1">
						<button
							onclick={() => (showPTZ = !showPTZ)}
							class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-white/10 {showPTZ
								? 'text-blue-400'
								: 'text-white/80'}"
							title="Toggle PTZ Controls"
						>
							<Crosshair class="size-4" />
							<span class="hidden sm:inline">PTZ</span>
						</button>
						<button
							onclick={toggleFullscreen}
							class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium text-white/80 transition-colors hover:bg-white/10 hover:text-white"
							title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
						>
							{#if isFullscreen}
								<Minimize class="size-4" />
							{:else}
								<Maximize class="size-4" />
							{/if}
						</button>
					</div>
				</div>

				<!-- ─── Count Badge (top center) ─── -->
				{#if trackCount > 0}
					<div class="absolute top-3 left-1/2 z-10 -translate-x-1/2">
						<div
							class="flex items-center gap-1.5 rounded-full border border-white/10 bg-black/60 px-3 py-1 backdrop-blur-sm"
						>
							<Eye class="size-3 text-blue-400" />
							<span class="font-mono text-xs font-bold text-white">{trackCount}</span>
							<span class="text-[10px] text-white/50">tracked</span>
						</div>
					</div>
				{/if}
			</div>

			<!-- ─── Stats Cards ─── -->
			<div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
				<div
					class="group rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/20"
				>
					<div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<Shield class="size-3.5 text-blue-400" />
						Detection Model
					</div>
					<div class="mt-1.5 text-sm font-semibold tracking-tight">{modelName}</div>
				</div>
				<div
					class="group rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/20"
				>
					<div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<Activity class="size-3.5 text-emerald-400" />
						Frame Rate
					</div>
					<div class="mt-1.5 text-sm font-semibold tracking-tight">{fps} FPS</div>
				</div>
				<div
					class="group rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/20"
				>
					<div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<HardDrive class="size-3.5 text-amber-400" />
						Bitrate
					</div>
					<div class="mt-1.5 text-sm font-semibold tracking-tight">{bitrate}</div>
				</div>
				<div
					class="group rounded-xl border bg-card p-3.5 shadow-sm transition-colors hover:border-primary/20"
				>
					<div class="flex items-center gap-2 text-xs font-medium text-muted-foreground">
						<Clock class="size-3.5 text-purple-400" />
						Uptime
					</div>
					<div class="mt-1.5 text-sm font-semibold tracking-tight">{uptime}</div>
				</div>
			</div>

			<!-- ─── Zone Occupancy ─── -->
			{#if zones.length > 0}
				<div class="rounded-xl border bg-card shadow-sm">
					<div class="flex items-center justify-between border-b px-4 py-3">
						<div class="flex items-center gap-2">
							<ImageIcon class="size-4 text-muted-foreground" />
							<h3 class="text-sm font-semibold tracking-tight">Zone Occupancy</h3>
						</div>
						<span class="text-xs text-muted-foreground">{zones.length} active zones</span>
					</div>
					<div
						class="grid grid-cols-1 gap-0 divide-y sm:grid-cols-3 sm:gap-0 sm:divide-x sm:divide-y-0"
					>
						{#each zones as zone}
							<div class="flex items-center gap-3 px-4 py-3">
								<div
									class="size-2.5 shrink-0 rounded-full"
									style="background-color: {zone.color}"
								></div>
								<div class="min-w-0 flex-1">
									<div class="truncate text-xs font-medium text-muted-foreground">{zone.name}</div>
									<div class="text-xl font-bold tracking-tight">{zoneCounts[zone.id] || 0}</div>
								</div>
								<div class="flex items-center gap-1 rounded-full bg-muted/50 px-2 py-0.5">
									<Users class="size-3 text-muted-foreground" />
									<span class="text-[10px] font-medium text-muted-foreground">objects</span>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}
		</div>

		<!-- ─── Right Sidebar: Activity Feed ─── -->
		<div class="flex w-full flex-col lg:w-80 xl:w-96">
			<div class="flex flex-1 flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
				<!-- Feed header -->
				<div class="border-b px-4 py-3">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2">
							<Activity class="size-4 text-blue-400" />
							<h3 class="text-sm font-semibold tracking-tight">Activity Feed</h3>
						</div>
						<span
							class="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] font-medium text-muted-foreground"
						>
							{activityLogs.length} events
						</span>
					</div>
					<!-- Filter tabs -->
					<div class="mt-2.5 flex gap-1 overflow-x-auto">
						<button
							onclick={() => (activeEventFilter = 'all')}
							class="shrink-0 rounded-md px-2 py-1 text-[11px] font-medium transition-colors {activeEventFilter ===
							'all'
								? 'bg-primary text-primary-foreground'
								: 'text-muted-foreground hover:bg-muted'}"
						>
							All
						</button>
						{#each Object.entries(eventTypeConfig) as [key, config]}
							<button
								onclick={() => (activeEventFilter = key)}
								class="shrink-0 rounded-md px-2 py-1 text-[11px] font-medium transition-colors {activeEventFilter ===
								key
									? 'bg-primary text-primary-foreground'
									: 'text-muted-foreground hover:bg-muted'}"
							>
								{config.label}
							</button>
						{/each}
					</div>
				</div>

				<!-- Feed content -->
				<div class="flex-1 overflow-y-auto">
					{#if filteredLogs.length === 0}
						<div class="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
							<Eye class="size-8 text-muted-foreground/30" />
							<p class="text-sm text-muted-foreground">Waiting for events...</p>
							<p class="text-xs text-muted-foreground/60">
								Activity will appear here as objects are detected
							</p>
						</div>
					{:else}
						<ul class="divide-y divide-border/30">
							{#each filteredLogs as log (log.id)}
								<li class="flex items-start gap-3 px-4 py-2.5 transition-colors hover:bg-muted/20">
									<!-- Event type indicator -->
									<div class="mt-0.5 shrink-0">
										<div
											class="flex size-6 items-center justify-center rounded-md {eventTypeConfig[
												log.type
											].bgColor}"
										>
											{#if log.type === 'person'}
												<Users class="size-3 {eventTypeConfig[log.type].color}" />
											{:else if log.type === 'vehicle'}
												<Car class="size-3 {eventTypeConfig[log.type].color}" />
											{:else if log.type === 'motion'}
												<Activity class="size-3 {eventTypeConfig[log.type].color}" />
											{:else if log.type === 'zone'}
												<Shield class="size-3 {eventTypeConfig[log.type].color}" />
											{:else}
												<AlertTriangle class="size-3 {eventTypeConfig[log.type].color}" />
											{/if}
										</div>
									</div>
									<div class="min-w-0 flex-1">
										<p class="text-xs leading-relaxed text-foreground/90">{log.message}</p>
										<div class="mt-0.5 flex items-center gap-2">
											<span class="font-mono text-[10px] text-muted-foreground">{log.time}</span>
											{#if log.zone}
												<span
													class="rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground"
													>{log.zone}</span
												>
											{/if}
										</div>
									</div>
								</li>
							{/each}
						</ul>
					{/if}
				</div>
			</div>
		</div>
	</div>

	<!-- ─── System Health Footer ─── -->
	<footer class="flex items-center justify-between border-t bg-card/50 px-4 py-2 backdrop-blur-sm">
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-1.5">
				<span class="size-1.5 rounded-full bg-emerald-500"></span>
				<span class="text-[11px] text-muted-foreground">System OK</span>
			</div>
			<div class="hidden items-center gap-1.5 sm:flex">
				<HardDrive class="size-3 text-muted-foreground" />
				<span class="text-[11px] text-muted-foreground">Storage: 324 GB free</span>
			</div>
		</div>
		<div class="flex items-center gap-4">
			<span class="text-[11px] text-muted-foreground"
				>Camera ID: {taskId?.slice(0, 8) ?? '—'}...</span
			>
			<span class="font-mono text-[11px] text-muted-foreground">{hudTime}</span>
		</div>
	</footer>
</div>
