<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { Button } from '$lib/components/ui/button/index.js';
	import {
		ChevronLeft,
		Maximize,
		Minimize,
		Camera,
		Settings,
		Shield,
		HardDrive,
		Clock,
		Eye,
		Users,
		Car,
		Activity,
		AlertTriangle,
		Crosshair,
		ImageIcon,
		VideoOff,
		Check,
		Loader2,
		Trash2,
		Pause,
		Play,
		X,
		ArrowDown
	} from '@lucide/svelte';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import * as Select from '$lib/components/ui/select/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import LiveHeatmap from '$lib/components/livestream/live-heatmap.svelte';
	import { onMount, onDestroy } from 'svelte';

	const taskId = $derived($page.params.taskId);

	interface Point {
		x: number;
		y: number;
		timestamp: number;
	}

	let heatmapPoints = $state<Point[]>([]);
	let showHeatmap = $state(false);

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
	let fps = $state(0);
	let errorMsg = $state<string | null>(null);
	let uptime = $state('00:00:00');
	let startTime = $state<number | null>(null);
	let storageGbFree = $state('...');
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
		severity?: 'critical' | 'warning' | 'info';
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

	// ─── NVR-style Feed Controls ───
	let isFeedPaused = $state(false);
	let pausedBuffer = $state<ActivityEvent[]>([]);
	let isAutoScrollEnabled = $state(true);
	let feedContainer: HTMLDivElement | null = $state(null);
	let hasNewEvents = $state(false);
	let eventCounts = $state<Record<string, number>>({});

	function classifySeverity(type: string): 'critical' | 'warning' | 'info' {
		if (type === 'alert' || type === 'capacity_warning' || type === 'wrong_way') return 'critical';
		if (type === 'zone') return 'warning';
		return 'info';
	}

	function addActivityLog(message: string, type: EventType, zone?: string) {
		const now = new Date();
		const timeStr = now.toLocaleTimeString([], {
			hour12: false,
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});

		const severity = classifySeverity(type);
		const newEvent: ActivityEvent = {
			time: timeStr,
			message,
			type,
			zone,
			id: crypto.randomUUID(),
			severity
		};

		// Track event counts
		eventCounts[type] = (eventCounts[type] || 0) + 1;
		eventCounts = { ...eventCounts };

		// Trigger highlight for high-priority events
		if (severity === 'critical') {
			hasActiveAlert = true;
			if (alertTimeout) clearTimeout(alertTimeout);
			alertTimeout = setTimeout(() => {
				hasActiveAlert = false;
			}, 4000);
		}

		if (isFeedPaused) {
			// Buffer events while paused
			pausedBuffer = [newEvent, ...pausedBuffer].slice(0, 100);
			hasNewEvents = true;
		} else {
			activityLogs = [newEvent, ...activityLogs].slice(0, 200);
			// Smart auto-scroll
			if (!isAutoScrollEnabled) {
				hasNewEvents = true;
			}
		}
	}

	function toggleFeedPause() {
		isFeedPaused = !isFeedPaused;
		if (!isFeedPaused && pausedBuffer.length > 0) {
			// Flush buffered events
			activityLogs = [...pausedBuffer, ...activityLogs].slice(0, 200);
			pausedBuffer = [];
			hasNewEvents = false;
		}
	}

	function clearActivityLogs() {
		activityLogs = [];
		pausedBuffer = [];
		eventCounts = {};
		hasNewEvents = false;
	}

	function scrollToLatest() {
		if (feedContainer) {
			feedContainer.scrollTop = 0;
			isAutoScrollEnabled = true;
			hasNewEvents = false;
		}
	}

	function handleFeedScroll() {
		if (!feedContainer) return;
		// If user scrolls near the top (where newest events are), re-enable auto-scroll
		const isNearTop = feedContainer.scrollTop < 20;
		isAutoScrollEnabled = isNearTop;
		if (isNearTop) {
			hasNewEvents = false;
		}
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

						// Add heatmap point if available
						if (data.point && data.point.x && data.point.y) {
							heatmapPoints.push({
								x: data.point.x,
								y: data.point.y,
								timestamp: data.timestamp ? data.timestamp * 1000 : Date.now()
							});
						}
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

	// ─── Lifecycle ───
	// ─── Fetch initial state from server (NVR-style persistence) ───
	async function fetchStreamStatus() {
		try {
			const res = await fetch(`http://localhost:8000/api/livestream/${taskId}/status`);
			if (res.ok) {
				const data = await res.json();
				if (data.started_at) {
					startTime = data.started_at * 1000; // Convert to ms
				}
			}
		} catch {
			// Stream may not be active yet
		}
	}

	async function fetchFpsNow() {
		try {
			const res = await fetch('http://localhost:8000/api/system/cameras');
			if (res.ok) {
				const data = await res.json();
				if (data.cameras) {
					const camStats = data.cameras.find((c: any) => c.id === taskId);
					if (camStats) {
						fps = camStats.detect_fps;
					}
				}
			}
		} catch {
			// silent
		}
	}

	async function fetchRecentEvents() {
		try {
			const res = await fetch(
				`http://localhost:8000/api/livestream/${taskId}/recent-events?limit=100`
			);
			if (res.ok) {
				const data = await res.json();
				if (data.events && data.events.length > 0) {
					const mapped = data.events.map(
						(ev: { type: string; message: string; zone?: string; timestamp?: number }) => {
							const evTime = ev.timestamp
								? new Date(ev.timestamp * 1000)
								: new Date();
							const severity = classifySeverity(ev.type);
							return {
								id: crypto.randomUUID(),
								time: evTime.toLocaleTimeString([], {
									hour12: false,
									hour: '2-digit',
									minute: '2-digit',
									second: '2-digit'
								}),
								message: ev.message,
								type: ev.type,
								zone: ev.zone,
								severity
							} as ActivityEvent;
						}
					);
					activityLogs = mapped;
					// Rebuild event counts from loaded history
					const counts: Record<string, number> = {};
					for (const ev of mapped) {
						counts[ev.type] = (counts[ev.type] || 0) + 1;
					}
					eventCounts = counts;
				}
			}
		} catch {
			// Activity feed will just start empty
		}
	}

	onMount(() => {
		// NVR-style: fetch server-side state first (uptime, FPS, recent events)
		fetchStreamStatus();
		fetchFpsNow();
		fetchRecentEvents();
		fetchCameraInfo();
		fetchAvailableModels();

		// Fetch storage once on mount
		fetch('http://localhost:8000/api/system/storage')
			.then((res) => res.json())
			.then((data) => {
				if (data.total) {
					storageGbFree = (data.total.total_gb - data.total.used_gb).toFixed(1);
				}
			})
			.catch((err) => console.error('Failed to load storage stats:', err));

		clockInterval = setInterval(() => {
			currentTime = new Date();

			// Calculate uptime from server-side start time (NVR-style)
			if (startTime) {
				const diffSeconds = Math.floor((Date.now() - startTime) / 1000);
				const h = Math.floor(diffSeconds / 3600);
				const m = Math.floor((diffSeconds % 3600) / 60);
				const s = diffSeconds % 60;
				uptime = [h, m, s].map((v) => v.toString().padStart(2, '0')).join(':');
			}

			// Poll FPS from system metrics
			fetchFpsNow();
		}, 5000); // Poll metrics and update uptime every 5s

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
</script>

<svelte:head>
	<title>{cameraName} · Live · Locus</title>
</svelte:head>

<div class="flex h-full flex-col overflow-hidden">
	<!-- ─── Header Bar ─── -->
	<header
		class="flex shrink-0 items-center justify-between border-b bg-card/50 px-3 py-2 backdrop-blur-sm"
	>
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
	<div class="flex min-h-0 flex-1 gap-3 overflow-hidden p-3 lg:flex-row">
		<!-- Left: Video + Stats -->
		<div class="flex min-h-0 min-w-0 flex-1 flex-col gap-2">
			<!-- Video Player -->
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div
				bind:this={videoContainer}
				class="group relative flex min-h-0 w-full flex-1 flex-col items-center justify-center overflow-hidden rounded-xl bg-black shadow-xl transition-all duration-500 {hasActiveAlert
					? 'border-2 border-red-500 shadow-[0_0_30px_rgba(239,68,68,0.4)]'
					: 'border border-border/50'}"
				style={isFullscreen ? 'height: 100vh;' : ''}
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

						{#if videoWidth > 0 && videoHeight > 0}
							<LiveHeatmap
								points={heatmapPoints}
								width={videoWidth}
								height={videoHeight}
								show={showHeatmap}
							/>
						{/if}
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

				<!-- Bottom left: model + FPS -->
				<div class="absolute bottom-3 left-3 z-10">
					<span class="font-mono text-[10px] text-white/40">
						{modelName} · {fps > 0 ? fps.toFixed(1) + 'fps' : 'Loading...'} · {resolution}
					</span>
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
						<!-- Control bar intentionally simplified -->
					</div>
					<div class="flex items-center gap-1">
						<button
							onclick={() => (showHeatmap = !showHeatmap)}
							class="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors hover:bg-white/10 {showHeatmap
								? 'text-fuchsia-400'
								: 'text-white/80'}"
							title="Toggle Heatmap"
						>
							<Activity class="size-4" />
							<span class="hidden sm:inline">Heatmap</span>
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

			<!-- ─── Stats Strip ─── -->
			<div
				class="flex shrink-0 items-center gap-3 overflow-x-auto rounded-lg border bg-card/60 px-3 py-1.5 backdrop-blur-sm"
			>
				<div class="flex shrink-0 items-center gap-1.5">
					<Shield class="size-3 text-blue-400" />
					<span class="text-[11px] text-muted-foreground">Model</span>
					<span class="text-[11px] font-semibold">{modelName}</span>
				</div>
				<span class="text-border">│</span>
				<div class="flex shrink-0 items-center gap-1.5">
					<Activity class="size-3 text-emerald-400" />
					<span class="text-[11px] font-semibold">{fps > 0 ? fps.toFixed(1) + ' FPS' : '...'}</span>
				</div>
				<span class="text-border">│</span>
				<div class="flex shrink-0 items-center gap-1.5">
					<Clock class="size-3 text-purple-400" />
					<span class="text-[11px] font-semibold">{uptime}</span>
				</div>
			</div>

			<!-- ─── Zone Occupancy (compact) ─── -->
			{#if zones.length > 0}
				<div
					class="flex shrink-0 items-center gap-3 overflow-x-auto rounded-lg border bg-card/60 px-3 py-1.5 backdrop-blur-sm"
				>
					<div class="flex shrink-0 items-center gap-1.5">
						<ImageIcon class="size-3 text-muted-foreground" />
						<span class="text-[11px] font-medium text-muted-foreground">Zones</span>
					</div>
					<span class="text-border">│</span>
					{#each zones as zone, i}
						<div class="flex shrink-0 items-center gap-1.5">
							<div
								class="size-2 shrink-0 rounded-full"
								style="background-color: {zone.color}"
							></div>
							<span class="text-[11px] text-muted-foreground">{zone.name}</span>
							<span class="text-[11px] font-bold">{zoneCounts[zone.id] || 0}</span>
						</div>
						{#if i < zones.length - 1}
							<span class="text-border">·</span>
						{/if}
					{/each}
				</div>
			{/if}
		</div>

		<!-- ─── Right Sidebar: Activity Feed (NVR-style) ─── -->
		<div class="hidden min-h-0 w-80 shrink-0 flex-col lg:flex xl:w-96">
			<div class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
				<!-- Feed header with toolbar -->
				<div class="border-b px-4 py-3">
					<div class="flex items-center justify-between">
						<div class="flex items-center gap-2">
							<Activity class="size-4 text-blue-400" />
							<h3 class="text-sm font-semibold tracking-tight">Activity Feed</h3>
							{#if isFeedPaused}
								<span
									class="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[9px] font-bold tracking-wider text-amber-400 uppercase"
									>Paused</span
								>
							{/if}
						</div>
						<div class="flex items-center gap-1">
							<!-- Event count badge -->
							<span
								class="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] font-medium text-muted-foreground"
							>
								{activityLogs.length}
								{#if isFeedPaused && pausedBuffer.length > 0}
									<span class="text-amber-400">+{pausedBuffer.length}</span>
								{/if}
							</span>
							<!-- Pause/Resume -->
							<button
								onclick={toggleFeedPause}
								class="flex size-6 items-center justify-center rounded-md transition-colors hover:bg-muted {isFeedPaused
									? 'text-amber-400'
									: 'text-muted-foreground hover:text-foreground'}"
								title={isFeedPaused ? 'Resume feed' : 'Pause feed'}
							>
								{#if isFeedPaused}
									<Play class="size-3" />
								{:else}
									<Pause class="size-3" />
								{/if}
							</button>
							<!-- Clear -->
							<button
								onclick={clearActivityLogs}
								class="flex size-6 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-red-500/10 hover:text-red-400"
								title="Clear all events"
							>
								<X class="size-3" />
							</button>
						</div>
					</div>

					<!-- Quick-glance event type summary bar -->
					{#if Object.keys(eventCounts).length > 0}
						<div class="mt-2 flex flex-wrap gap-1.5">
							{#each Object.entries(eventCounts) as [type, count]}
								{@const cfg = eventTypeConfig[type] || {
									label: type,
									color: 'text-zinc-400',
									bgColor: 'bg-zinc-500/15'
								}}
								<div class="flex items-center gap-1 rounded-full {cfg.bgColor} px-2 py-0.5">
									<span class="size-1.5 rounded-full {cfg.color.replace('text-', 'bg-')}"></span>
									<span class="text-[10px] font-medium {cfg.color}">{count}</span>
								</div>
							{/each}
						</div>
					{/if}

					<!-- Filter tabs with count badges -->
					<div class="mt-2.5 flex gap-1 overflow-x-auto">
						<button
							onclick={() => (activeEventFilter = 'all')}
							class="shrink-0 rounded-md px-2 py-1 text-[11px] font-medium transition-colors {activeEventFilter ===
							'all'
								? 'bg-primary text-primary-foreground'
								: 'text-muted-foreground hover:bg-muted'}"
						>
							All
							{#if activityLogs.length > 0}
								<span class="ml-0.5 text-[9px] opacity-70">({activityLogs.length})</span>
							{/if}
						</button>
						{#each Object.entries(eventTypeConfig) as [key, config]}
							{@const count = eventCounts[key] || 0}
							{#if count > 0}
								<button
									onclick={() => (activeEventFilter = key)}
									class="shrink-0 rounded-md px-2 py-1 text-[11px] font-medium transition-colors {activeEventFilter ===
									key
										? 'bg-primary text-primary-foreground'
										: 'text-muted-foreground hover:bg-muted'}"
								>
									{config.label}
									<span class="ml-0.5 text-[9px] opacity-70">({count})</span>
								</button>
							{/if}
						{/each}
					</div>
				</div>

				<!-- Feed content with smart auto-scroll -->
				<div
					class="relative flex-1 overflow-y-auto"
					bind:this={feedContainer}
					onscroll={handleFeedScroll}
				>
					{#if filteredLogs.length === 0}
						<div class="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
							<div class="flex size-12 items-center justify-center rounded-full bg-muted/30">
								<Eye class="size-5 text-muted-foreground/40" />
							</div>
							<div>
								<p class="text-sm font-medium text-muted-foreground">Waiting for events</p>
								<p class="mt-1 text-xs text-muted-foreground/50">
									Events will appear as objects enter the camera view
								</p>
							</div>
							<div class="flex items-center gap-1.5 rounded-full bg-muted/30 px-3 py-1">
								{#if isConnected}
									<span class="size-1.5 rounded-full bg-emerald-500"></span>
									<span class="text-[10px] text-emerald-400">SSE Connected</span>
								{:else}
									<span class="size-1.5 animate-pulse rounded-full bg-amber-500"></span>
									<span class="text-[10px] text-amber-400">Connecting...</span>
								{/if}
							</div>
						</div>
					{:else}
						<ul>
							{#each filteredLogs as log, i (log.id)}
								{@const config = eventTypeConfig[log.type] || {
									color: 'text-zinc-400',
									bgColor: 'bg-zinc-500/15'
								}}
								{@const isCritical = log.severity === 'critical'}
								{@const isWarning = log.severity === 'warning'}
								<li
									class="relative flex items-start gap-3 border-b border-border/20 px-4 py-2.5 transition-all duration-300 hover:bg-muted/20
									{isCritical ? 'bg-red-500/5' : ''}
									{isWarning ? 'bg-purple-500/5' : ''}
									{i === 0 ? 'animate-[slideDown_0.3s_ease-out]' : ''}"
								>
									<!-- Severity accent bar -->
									{#if isCritical}
										<div
											class="absolute top-0 bottom-0 left-0 w-[3px] animate-pulse rounded-r bg-red-500"
										></div>
									{:else if isWarning}
										<div
											class="absolute top-0 bottom-0 left-0 w-[3px] rounded-r bg-purple-500/60"
										></div>
									{/if}

									<!-- Event type indicator -->
									<div class="mt-0.5 shrink-0">
										<div
											class="flex size-6 items-center justify-center rounded-md {config.bgColor} {isCritical
												? 'ring-1 ring-red-500/30'
												: ''}"
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
												<Crosshair class="size-3 {config.color}" />
											{/if}
										</div>
									</div>
									<div class="min-w-0 flex-1">
										<p
											class="text-xs leading-relaxed {isCritical
												? 'font-medium text-foreground'
												: 'text-foreground/90'}"
										>
											{log.message}
										</p>
										<div class="mt-0.5 flex items-center gap-2">
											<span class="font-mono text-[10px] text-muted-foreground">{log.time}</span>
											{#if log.zone}
												<span
													class="rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground"
													>{log.zone}</span
												>
											{/if}
											{#if isCritical}
												<span
													class="rounded bg-red-500/15 px-1 py-0.5 text-[9px] font-bold text-red-400 uppercase"
													>Alert</span
												>
											{/if}
										</div>
									</div>
								</li>
							{/each}
						</ul>
					{/if}

					<!-- "New events" floating pill (appears when scrolled away from top) -->
					{#if hasNewEvents}
						<button
							onclick={scrollToLatest}
							class="absolute right-3 bottom-3 z-10 flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/15 px-3 py-1.5 text-xs font-medium text-blue-400 shadow-lg backdrop-blur-sm transition-all hover:bg-blue-500/25"
						>
							<ArrowDown class="size-3" />
							New events
							{#if isFeedPaused && pausedBuffer.length > 0}
								({pausedBuffer.length})
							{/if}
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>

	<!-- ─── System Health Footer ─── -->
	<footer
		class="flex shrink-0 items-center justify-between border-t bg-card/50 px-3 py-1.5 backdrop-blur-sm"
	>
		<div class="flex items-center gap-4">
			<div class="flex items-center gap-1.5">
				<span class="size-1.5 rounded-full bg-emerald-500"></span>
				<span class="text-[11px] text-muted-foreground">System OK</span>
			</div>
			<div class="hidden items-center gap-1.5 sm:flex">
				<HardDrive class="size-3 text-muted-foreground" />
				<span class="text-[11px] text-muted-foreground">Storage: {storageGbFree} GB free</span>
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
		<Dialog.Footer class="gap-2 sm:justify-end">
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
