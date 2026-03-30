<script lang="ts">
	import {
		Activity,
		Users,
		Car,
		Shield,
		AlertTriangle,
		Crosshair,
		Eye,
		Pause,
		Play,
		X,
		ArrowDown
	} from '@lucide/svelte';

	// ─── Types ───
	type EventType = string;
	interface ActivityEvent {
		id: string;
		time: string;
		timestamp?: number; // Unix seconds
		message: string;
		type: EventType;
		zone?: string;
		severity?: 'critical' | 'warning' | 'info';
	}

	// ─── Props ───
	let {
		eventTypeConfig,
		isConnected = false,
		hasActiveAlert = $bindable(false)
	}: {
		eventTypeConfig: Record<string, { label: string; color: string; bgColor: string }>;
		isConnected?: boolean;
		hasActiveAlert?: boolean;
	} = $props();

	// ─── Feed State ───
	let activityLogs = $state<ActivityEvent[]>([]);
	let isFeedPaused = $state(false);
	let pausedBuffer = $state<ActivityEvent[]>([]);
	let isAutoScrollEnabled = $state(true);
	let feedContainer: HTMLDivElement | null = $state(null);
	let hasNewEvents = $state(false);
	let eventCounts = $state<Record<string, number>>({});
	let activeEventFilter = $state<string>('all');
	let alertTimeout: ReturnType<typeof setTimeout> | null = null;

	let filteredLogs = $derived(
		activeEventFilter === 'all'
			? activityLogs
			: activityLogs.filter((l) => l.type === activeEventFilter)
	);

	// ─── Helpers ───
	function relativeTime(ts: number): string {
		const diff = Math.floor(Date.now() / 1000 - ts);
		if (diff < 60) return `${diff}s ago`;
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
		return `${Math.floor(diff / 86400)}d ago`;
	}

	// Tick every 30s to keep relative times current
	$effect(() => {
		const interval = setInterval(() => {
			activityLogs = [...activityLogs];
		}, 30_000);
		return () => clearInterval(interval);
	});

	function classifySeverity(type: string): 'critical' | 'warning' | 'info' {
		if (type === 'alert' || type === 'capacity_warning' || type === 'wrong_way') return 'critical';
		if (type === 'zone') return 'warning';
		return 'info';
	}

	export function addEvent(message: string, type: EventType, zone?: string) {
		const now = new Date();
		const ts = Date.now() / 1000;
		const timeStr = now.toLocaleTimeString([], {
			hour12: false,
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});

		const severity = classifySeverity(type);
		const newEvent: ActivityEvent = {
			time: timeStr,
			timestamp: ts,
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
			pausedBuffer = [newEvent, ...pausedBuffer].slice(0, 100);
			hasNewEvents = true;
		} else {
			activityLogs = [newEvent, ...activityLogs].slice(0, 200);
			if (!isAutoScrollEnabled) {
				hasNewEvents = true;
			}
		}
	}

	export function loadEvents(
		events: { type: string; message: string; zone?: string; timestamp?: number }[]
	) {
		if (!events.length) return;
		const mapped = events.map((ev) => {
			const evTime = ev.timestamp ? new Date(ev.timestamp * 1000) : new Date();
			const severity = classifySeverity(ev.type);
			return {
				id: crypto.randomUUID(),
				time: evTime.toLocaleTimeString([], {
					hour12: false,
					hour: '2-digit',
					minute: '2-digit',
					second: '2-digit'
				}),
				timestamp: ev.timestamp,
				message: ev.message,
				type: ev.type,
				zone: ev.zone,
				severity
			} as ActivityEvent;
		});
		activityLogs = mapped;
		const counts: Record<string, number> = {};
		for (const ev of mapped) {
			counts[ev.type] = (counts[ev.type] || 0) + 1;
		}
		eventCounts = counts;
	}

	function toggleFeedPause() {
		isFeedPaused = !isFeedPaused;
		if (!isFeedPaused && pausedBuffer.length > 0) {
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
		const isNearTop = feedContainer.scrollTop < 20;
		isAutoScrollEnabled = isNearTop;
		if (isNearTop) {
			hasNewEvents = false;
		}
	}
</script>

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
					<span
						class="rounded-full bg-muted px-2 py-0.5 font-mono text-[10px] font-medium text-muted-foreground"
					>
						{activityLogs.length}
						{#if isFeedPaused && pausedBuffer.length > 0}
							<span class="text-amber-400">+{pausedBuffer.length}</span>
						{/if}
					</span>
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
							{#if isCritical}
								<div
									class="absolute top-0 bottom-0 left-0 w-[3px] animate-pulse rounded-r bg-red-500"
								></div>
							{:else if isWarning}
								<div
									class="absolute top-0 bottom-0 left-0 w-[3px] rounded-r bg-purple-500/60"
								></div>
							{/if}

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
									<span
									class="cursor-default font-mono text-[10px] text-muted-foreground"
									title={log.timestamp
										? new Date(log.timestamp * 1000).toLocaleString()
										: log.time}
								>
									{log.timestamp ? relativeTime(log.timestamp) : log.time}
								</span>
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
