<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
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
		ImageIcon,
		VideoOff,
		Check,
		Loader2,
		Trash2
	} from '@lucide/svelte';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Select from '$lib/components/ui/select/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { onMount, onDestroy } from 'svelte';

	const taskId = $derived($page.params.taskId);

	// ─── Camera State (loaded from backend) ───
	let cameraName = $state('Loading...');
	let cameraStatus = $state<'live' | 'connecting' | 'offline' | 'error'>('connecting');
	let cameraType = $state<'webcam' | 'rtsp'>('rtsp');
	let cameraUrl = $state('');
	let modelName = $state('YOLOv11n');
	let videoWidth = $state(0);
	let videoHeight = $state(0);
	let resolution = $derived(
		videoWidth && videoHeight ? `${videoWidth}×${videoHeight}` : 'Loading...'
	);
	let fps = $state(24);
	let bitrate = $state('4.2 Mbps');
	let errorMsg = $state<string | null>(null);
	let uptime = $state('--:--:--');
	let isSaving = $state(false);
	let isSettingsOpen = $state(false);
	let isDeleteDialogOpen = $state(false);
	let isDeleting = $state(false);
	let availableModels = $state<string[]>([]);

	// ─── Detection State (loaded from backend) ───
	let zones = $state<any[]>([]);
	let detectionClasses = $state<string[]>([]);
	let trackCount = $state(0);
	let zoneCounts = $state<Record<string, number>>({});

	// Fetch camera details from backend
	async function fetchCameraInfo() {
		try {
			const res = await fetch(`http://localhost:8000/api/cameras/${taskId}`);
			if (res.ok) {
				const data = await res.json();
				cameraName = data.name;
				cameraType = data.type as 'webcam' | 'rtsp';
				cameraUrl = data.url || '';
				modelName = data.model_name || 'YOLOv11n';
				cameraStatus = 'live';

				// Parse zones if stored as JSON string
				if (data.zones) {
					try {
						const parsedZones =
							typeof data.zones === 'string' ? JSON.parse(data.zones) : data.zones;
						zones = parsedZones;
						// Initialize zone counts from parsed zones
						const counts: Record<string, number> = {};
						for (const z of parsedZones) {
							counts[z.id] = 0;
						}
						zoneCounts = counts;
					} catch {
						zones = [];
					}
				}

				// Parse detection classes
				if (data.classes) {
					try {
						detectionClasses =
							typeof data.classes === 'string' ? JSON.parse(data.classes) : data.classes;
					} catch {
						detectionClasses = [];
					}
				}
			} else {
				errorMsg = 'Camera not found';
				cameraStatus = 'error';
			}
		} catch (err) {
			errorMsg = 'Failed to connect to backend';
			cameraStatus = 'error';
		}
	}

	async function fetchAvailableModels() {
		try {
			const res = await fetch('http://localhost:8000/api/cameras/models');
			if (res.ok) {
				availableModels = await res.json();
			}
		} catch (err) {
			console.error('Failed to fetch models:', err);
		}
	}

	async function saveSettings() {
		try {
			isSaving = true;
			const res = await fetch(`http://localhost:8000/api/cameras/${taskId}`, {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					name: cameraName,
					model_name: modelName
				})
			});
			if (res.ok) {
				isSettingsOpen = false;
				// The stream session should probably be restarted to apply the certain model changes
				// but for now we just update the UI state.
			} else {
				alert('Failed to save settings');
			}
		} catch (err) {
			console.error(err);
			alert('Error saving settings');
		} finally {
			isSaving = false;
		}
	}

	async function deleteCamera() {
		try {
			isDeleting = true;
			const res = await fetch(`http://localhost:8000/api/cameras/${taskId}`, {
				method: 'DELETE'
			});
			if (res.ok) {
				goto('/livestream');
			} else {
				const data = await res.json();
				alert(data.detail || 'Failed to delete camera');
			}
		} catch (err) {
			console.error(err);
			alert('Error deleting camera');
		} finally {
			isDeleting = false;
			isDeleteDialogOpen = false;
		}
	}

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
	type EventType = string;
	interface ActivityEvent {
		id: string;
		time: string;
		message: string;
		type: EventType;
		zone?: string;
	}

	const PALETTE = [
		{ color: 'text-blue-400', bgColor: 'bg-blue-500/15' },
		{ color: 'text-amber-400', bgColor: 'bg-amber-500/15' },
		{ color: 'text-emerald-400', bgColor: 'bg-emerald-500/15' },
		{ color: 'text-fuchsia-400', bgColor: 'bg-fuchsia-500/15' },
		{ color: 'text-cyan-400', bgColor: 'bg-cyan-500/15' },
		{ color: 'text-rose-400', bgColor: 'bg-rose-500/15' }
	];

	let eventTypeConfig = $derived.by(() => {
		const config: Record<string, { label: string; color: string; bgColor: string }> = {
			zone: { label: 'Zone Entry', color: 'text-purple-400', bgColor: 'bg-purple-500/15' },
			alert: { label: 'Alert', color: 'text-red-400', bgColor: 'bg-red-500/15' },
			capacity_warning: {
				label: 'Capacity Warning',
				color: 'text-rose-500',
				bgColor: 'bg-rose-500/20'
			},
			wrong_way: { label: 'Wrong Way', color: 'text-orange-500', bgColor: 'bg-orange-500/20' },
			motion: { label: 'Motion', color: 'text-emerald-400', bgColor: 'bg-emerald-500/15' }
		};

		if (detectionClasses && detectionClasses.length > 0) {
			detectionClasses.forEach((cls, idx) => {
				const c = PALETTE[idx % PALETTE.length];
				config[cls.toLowerCase()] = { label: cls.charAt(0).toUpperCase() + cls.slice(1), ...c };
			});
		} else {
			// Fallback defaults
			config['person'] = { label: 'Person', color: 'text-blue-400', bgColor: 'bg-blue-500/15' };
			config['vehicle'] = { label: 'Vehicle', color: 'text-amber-400', bgColor: 'bg-amber-500/15' };
		}

		return config;
	});

	let activityLogs = $state<ActivityEvent[]>([]);
	let hasActiveAlert = $state(false);
	let alertTimeout: ReturnType<typeof setTimeout> | null = null;

	function addActivityLog(message: string, type: EventType, zone?: string) {
		const now = new Date();
		const timeStr = now.toLocaleTimeString([], {
			hour12: false,
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});

		const newEvent: ActivityEvent = { time: timeStr, message, type, zone, id: crypto.randomUUID() };

		// Trigger highlight for high-priority events
		if (
			type === 'alert' ||
			type === 'zone' ||
			type === 'capacity_warning' ||
			type === 'wrong_way'
		) {
			hasActiveAlert = true;
			if (alertTimeout) clearTimeout(alertTimeout);
			alertTimeout = setTimeout(() => {
				hasActiveAlert = false;
			}, 4000);
		}

		activityLogs = [newEvent, ...activityLogs].slice(0, 100);
	}

	let filteredLogs = $derived(
		activeEventFilter === 'all'
			? activityLogs
			: activityLogs.filter((l) => l.type === activeEventFilter)
	);

	// ─── Real-time Event Sink (Server-Sent Events) ───
	let eventSource: EventSource | null = null;
	let isConnected = $state(false);

	$effect(() => {
		// Only run in the browser
		if (typeof window !== 'undefined') {
			eventSource = new EventSource(`http://localhost:8000/api/livestream/${taskId}/events`);

			eventSource.onopen = () => {
				isConnected = true;
				console.log('Connected to Livestream Events via SSE');
			};

			eventSource.onmessage = (event) => {
				try {
					const data = JSON.parse(event.data);

					if (data.type === 'zone_update') {
						// Update zone counts and total from the backend's AnalyticsEngine
						if (data.zone_counts) {
							zoneCounts = { ...zoneCounts, ...data.zone_counts };
						}
						if (data.total_count !== undefined) {
							trackCount = data.total_count;
						}
					} else {
						// Regular detection event — add to activity log
						addActivityLog(data.message, data.type, data.zone);
					}
				} catch (e) {
					console.error('Failed to parse SSE event:', e);
				}
			};

			eventSource.onerror = (error) => {
				console.error('SSE connection error:', error);
				isConnected = false;
				// EventSource automatically tries to reconnect
			};

			// Cleanup on dismount
			return () => {
				if (eventSource) {
					eventSource.close();
					isConnected = false;
				}
			};
		}
	});

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
		fetchCameraInfo();
		fetchAvailableModels();

		clockInterval = setInterval(() => {
			currentTime = new Date();
		}, 1000);
		document.addEventListener('fullscreenchange', handleFullscreenChange);
	});

	onDestroy(() => {
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
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					<Button variant="ghost" size="icon" class="size-8 text-muted-foreground hover:text-foreground">
						<Settings class="size-4" />
					</Button>
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end" class="w-48">
					<DropdownMenu.Label>Camera Options</DropdownMenu.Label>
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
						Delete Camera
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
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
				class="group relative flex w-full flex-col items-center justify-center overflow-hidden rounded-xl bg-black shadow-xl transition-all duration-500 {hasActiveAlert
					? 'border-2 border-red-500 shadow-[0_0_30px_rgba(239,68,68,0.4)]'
					: 'border border-border/50'}"
				style={isFullscreen ? 'height: 100vh;' : 'height: calc(100vh - 18rem); min-height: 24rem;'}
				onmousemove={handleVideoMouseMove}
				onmouseleave={handleVideoMouseLeave}
			>
				<div class="relative aspect-video w-full" style="max-height: 100%;">
					<div
						class="absolute inset-0 bg-black {hasActiveAlert
							? 'bg-red-950/20'
							: ''} flex items-center justify-center overflow-hidden rounded-lg transition-colors duration-500"
					>
						{#if isConnected}
							<img
								src={`http://localhost:8000/api/livestream/${taskId}/video`}
								alt="Live Video Feed"
								class="h-full w-full object-contain"
								bind:naturalWidth={videoWidth}
								bind:naturalHeight={videoHeight}
							/>
						{:else}
							<div class="flex flex-col items-center justify-center gap-4 text-zinc-500">
								<VideoOff class="size-8 opacity-50" />
								<span class="text-sm">Connecting to stream...</span>
							</div>
						{/if}

						<!-- Scanline effect overlay -->
						<div
							class="pointer-events-none absolute inset-0 bg-[repeating-linear-gradient(0deg,transparent,transparent_2px,rgba(0,0,0,0.03)_2px,rgba(0,0,0,0.03)_4px)]"
						></div>
					</div>

					<!-- Canvas overlay for detection boxes -->
					<canvas class="pointer-events-none absolute inset-0 size-full"></canvas>
				</div>

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
								{@const config = eventTypeConfig[log.type] || {
									color: 'text-zinc-400',
									bgColor: 'bg-zinc-500/15'
								}}
								<li class="flex items-start gap-3 px-4 py-2.5 transition-colors hover:bg-muted/20">
									<!-- Event type indicator -->
									<div class="mt-0.5 shrink-0">
										<div
											class="flex size-6 items-center justify-center rounded-md {config.bgColor}"
										>
											{#if log.type === 'person'}
												<Users class="size-3 {config.color}" />
											{:else if log.type === 'vehicle'}
												<Car class="size-3 {config.color}" />
											{:else if log.type === 'motion'}
												<Activity class="size-3 {config.color}" />
											{:else if log.type === 'zone'}
												<Shield class="size-3 {config.color}" />
											{:else if log.type === 'alert' || log.type === 'capacity_warning' || log.type === 'wrong_way'}
												<AlertTriangle class="size-3 {config.color}" />
											{:else}
												<!-- Generic fallback for arbitrary dynamic YOLO classes -->
												<Crosshair class="size-3 {config.color}" />
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

<Dialog.Root bind:open={isSettingsOpen}>
	<Dialog.Content class="sm:max-w-[425px]">
		<Dialog.Header>
			<Dialog.Title>Camera Settings</Dialog.Title>
			<Dialog.Description>Update camera name and AI model configuration.</Dialog.Description>
		</Dialog.Header>

		<div class="grid gap-4 py-4">
			<div class="grid gap-2">
				<Label for="name">Camera Name</Label>
				<Input id="name" bind:value={cameraName} placeholder="e.g. Front Door" />
			</div>
			<div class="grid gap-2">
				<Label for="model">Inference Model</Label>
				<Select.Root type="single" bind:value={modelName}>
					<Select.Trigger id="model" placeholder="Select AI Model" />
					<Select.Content>
						{#each availableModels as model}
							<Select.Item value={model}>{model}</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>
				<p class="text-[10px] text-muted-foreground">
					Model changes will apply next time the stream is started.
				</p>
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
				Delete Camera
			</Dialog.Title>
			<Dialog.Description>
				Are you sure you want to delete <strong>{cameraName}</strong>? This action cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		<Dialog.Footer class="gap-2 sm:gap-0">
			<Button variant="outline" onclick={() => (isDeleteDialogOpen = false)}>Cancel</Button>
			<Button variant="destructive" onclick={deleteCamera} disabled={isDeleting}>
				{#if isDeleting}
					<Loader2 class="mr-2 size-4 animate-spin" />
					Deleting...
				{:else}
					<Trash2 class="mr-2 size-4" />
					Delete Camera
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
