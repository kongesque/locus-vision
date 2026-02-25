<script lang="ts">
	import { page } from '$app/stores';
	import { AspectRatio } from '$lib/components/ui/aspect-ratio/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { ChevronLeft, Loader2, Download, Share2, FileJson } from '@lucide/svelte';
	import { onMount, onDestroy } from 'svelte';

	let { data } = $props();

	let taskId = $derived(data.taskId);
	let task = $derived(data.task as any);

	let videoSrc = $state<string | null>(null);
	let status = $state<'loading' | 'processing' | 'ready' | 'error'>('loading');
	let pollInterval: NodeJS.Timeout;

	// Initialize state based on loaded data
	$effect(() => {
		if (task) {
			if (task.status === 'completed') {
				status = 'ready';
				videoSrc = `http://localhost:8000/api/video/${taskId}/result`;
			} else if (task.status === 'failed') {
				status = 'error';
			} else {
				status = 'processing';
			}
		}
	});

	async function checkStatus() {
		// If already ready, no need to check, unless we want to handle re-checks?
		if (status === 'ready') return;

		try {
			const res = await fetch(`http://localhost:8000/api/video/${taskId}/result`);

			if (res.status === 200) {
				// Video is ready
				videoSrc = `http://localhost:8000/api/video/${taskId}/result`;
				status = 'ready';
				stopPolling();
			} else if (res.status === 202) {
				// Still processing
				status = 'processing';
			} else {
				// 404 or other
				// If we know it failed from metadata, we can show error.
				// Or if it's 404 but we expect it to be processing, maybe it takes time to appear?
				// For now, if 404, valid task ID -> processing or queued (unless very old).
				// But `result` endpoint returns 202 if pending/processing/not found but valid?
				// Actually my backend returns 202 if pending. 404 if weird?
				// Let's assume 202.
				if (status !== 'processing') status = 'loading';
			}
		} catch (e) {
			console.error('Error checking status', e);
			// Don't immediately set error on network blip
		}
	}

	function startPolling() {
		if (status === 'ready' || status === 'error') return;
		checkStatus(); // Initial check
		pollInterval = setInterval(checkStatus, 2000);
	}

	function stopPolling() {
		if (pollInterval) clearInterval(pollInterval);
	}

	onMount(() => {
		startPolling();
	});

	onDestroy(() => {
		stopPolling();
	});
</script>

<svelte:head>
	<title>{task ? task.filename : 'Task Result'} · Locus</title>
</svelte:head>

<div class="flex flex-1 flex-col gap-4 p-4">
	<div class="mb-2 flex items-center justify-between">
		<div class="flex items-center gap-4">
			<Button variant="ghost" size="icon" href="/video-analytics">
				<ChevronLeft class="h-4 w-4" />
			</Button>
			<h1 class="text-2xl font-bold tracking-tight">
				{task ? task.filename : `Task ${taskId.slice(0, 8)}`}
			</h1>
		</div>
		<div class="flex items-center gap-2">
			{#if status === 'ready'}
				<Button size="sm" class="gap-2" href={videoSrc} download>
					<Download class="h-4 w-4" />
					Export Video
				</Button>
			{/if}
			<div class="ml-4 flex items-center gap-2">
				<span class="relative flex h-3 w-3">
					{#if status === 'processing' || status === 'loading'}
						<span
							class="absolute inline-flex h-full w-full animate-ping rounded-full bg-yellow-400 opacity-75"
						></span>
						<span class="relative inline-flex h-3 w-3 rounded-full bg-yellow-500"></span>
					{:else if status === 'ready'}
						<span
							class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"
						></span>
						<span class="relative inline-flex h-3 w-3 rounded-full bg-green-500"></span>
					{:else}
						<span class="relative inline-flex h-3 w-3 rounded-full bg-red-500"></span>
					{/if}
				</span>
				<span class="text-sm font-medium text-muted-foreground capitalize">
					{status === 'loading' ? 'connecting' : status}
				</span>
			</div>
		</div>
	</div>

	{#if status === 'error'}
		<div class="rounded-md border border-red-500/20 bg-red-500/10 p-4 text-red-500">
			Failed to load video result.
		</div>
	{/if}

	<div class="flex flex-1 flex-row gap-4">
		<div class="mx-auto flex w-full max-w-5xl flex-col gap-4">
			<div class="relative overflow-hidden rounded-lg border bg-black shadow-lg">
				<AspectRatio ratio={16 / 9} class="group relative max-h-[80vh]">
					{#if status === 'ready' && videoSrc}
						<!-- svelte-ignore a11y_media_has_caption -->
						<video
							src={videoSrc}
							class="h-full w-full object-contain"
							controls
							autoplay
							loop
							playsinline
							crossorigin="anonymous"
						></video>
					{:else if status === 'processing' || status === 'loading'}
						<div
							class="flex h-full flex-col items-center justify-center gap-4 text-muted-foreground"
						>
							<Loader2 class="h-8 w-8 animate-spin" />
							<p>Processing video task...</p>
							<p class="text-xs opacity-70">
								This typically takes 10-30 seconds depending on video length.
							</p>
						</div>
					{/if}
				</AspectRatio>
			</div>

			<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
				<div class="grid grid-cols-2 gap-4 md:col-span-2">
					<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
						<div class="text-sm font-semibold text-muted-foreground">Detection Model</div>
						<div class="mt-1 text-2xl font-bold tracking-tight">
							{task ? task.model_name || 'yolo11n' : 'Loading...'}
						</div>
					</div>
					<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
						<div class="text-sm font-semibold text-muted-foreground">Duration Analyzed</div>
						<div class="mt-1 text-2xl font-bold tracking-tight">
							{task ? task.duration || '--:--' : '--:--'}
						</div>
					</div>

					<!-- Add a timeline scrub context -->
					<div
						class="col-span-2 flex flex-col gap-2 rounded-lg border bg-card p-4 text-card-foreground shadow-sm"
					>
						<div class="text-sm font-semibold text-muted-foreground">Analysis Context</div>
						<div class="text-sm">
							Processed using high-accuracy tracking at 12fps. Export data to view raw JSON
							detections for every frame, tracked via DeepSort.
						</div>
						<div class="mt-2">
							<Button
								variant="secondary"
								size="sm"
								class="gap-2"
								href={`http://localhost:8000/api/video/${taskId}/data`}
								download
							>
								<FileJson class="h-4 w-4" />
								Export Raw Data (JSON)
							</Button>
						</div>
					</div>
				</div>

				<div
					class="flex min-h-[200px] flex-col overflow-hidden rounded-lg border bg-card shadow-sm"
				>
					<div class="border-b bg-muted/30 p-4">
						<h3 class="text-sm font-semibold tracking-tight text-muted-foreground">
							Detected Activity Summary
						</h3>
					</div>
					<div class="flex flex-1 flex-col p-4">
						{#if status === 'ready' && task}
							<div class="mb-4 flex flex-col items-center justify-center border-b pb-4">
								<div class="mb-1 text-sm text-muted-foreground">Total Unique Objects</div>
								<div class="text-5xl font-bold text-primary">{task.total_count || 0}</div>
							</div>

							<!-- Render Zone Counts if they exist -->
							{@const parsedZoneCounts = task.zone_counts ? JSON.parse(task.zone_counts) : null}
							{#if parsedZoneCounts && Object.keys(parsedZoneCounts).length > 0}
								<div class="grid w-full grid-cols-2 gap-2">
									{#each Object.entries(parsedZoneCounts) as [zoneId, count]}
										<div class="rounded bg-muted/30 p-2 text-center">
											<div class="truncate text-xs text-muted-foreground" title={zoneId}>
												{zoneId.length > 8 ? `Zone ${zoneId.slice(0, 4)}` : zoneId}
											</div>
											<div class="text-xl font-bold">{count}</div>
										</div>
									{/each}
								</div>
							{:else}
								<div class="mt-4 text-center text-sm text-muted-foreground">
									No zones defined for this task.
								</div>
							{/if}
						{:else}
							<div
								class="flex flex-1 flex-col items-center justify-center text-center text-sm text-muted-foreground"
							>
								Waiting for analysis to complete...
							</div>
						{/if}
					</div>
				</div>
			</div>
		</div>
	</div>
</div>
