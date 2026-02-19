<script lang="ts">
	import { page } from '$app/stores';
	import historyData from '../../../../../data/video_history.json'; // Keep for metadata fallback
	import { AspectRatio } from '$lib/components/ui/aspect-ratio/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { ChevronLeft, Loader2 } from '@lucide/svelte';
	import { onMount, onDestroy } from 'svelte';

	let taskId = $derived($page.params.taskId ?? '');

	// Fallback metadata if available
	let task = $derived(historyData.find((t) => t.id === taskId));

	let videoSrc = $state<string | null>(null);
	let status = $state<'loading' | 'processing' | 'ready' | 'error'>('loading');
	let pollInterval: NodeJS.Timeout;

	async function checkStatus() {
		try {
			const res = await fetch(`http://localhost:8000/api/video/${taskId}/result`);

			if (res.status === 200) {
				// Video is ready
				// We can use the URL directly since our backend serves it
				videoSrc = `http://localhost:8000/api/video/${taskId}/result`;
				status = 'ready';
				stopPolling();
			} else if (res.status === 202) {
				// Still processing
				status = 'processing';
			} else {
				status = 'error';
				stopPolling();
			}
		} catch (e) {
			console.error('Error checking status', e);
			status = 'error';
			stopPolling();
		}
	}

	function startPolling() {
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
	<title>{task ? task.name : 'Task Result'} · Locus</title>
</svelte:head>

<div class="flex flex-1 flex-col gap-4 p-4">
	<div class="flex items-center gap-4">
		<Button variant="ghost" size="icon" href="/video-analytics">
			<ChevronLeft class="h-4 w-4" />
		</Button>
		<h1 class="text-2xl font-bold tracking-tight">
			{task ? task.name : `Task ${taskId.slice(0, 8)}`}
		</h1>
		{#if status === 'processing'}
			<div class="flex items-center gap-2 text-sm text-muted-foreground">
				<Loader2 class="h-4 w-4 animate-spin" />
				Processing...
			</div>
		{/if}
	</div>

	<div class="flex flex-1 flex-col gap-4 lg:flex-row">
		<div class="flex w-full flex-col gap-4 lg:w-3/4">
			<!-- Video Player -->
			<div class="group relative overflow-hidden rounded-lg border bg-black shadow-sm">
				<AspectRatio ratio={16 / 9} class="flex max-h-[70vh] items-center justify-center">
					{#if status === 'ready' && videoSrc}
						<!-- svelte-ignore a11y_media_has_caption -->
						<video src={videoSrc} class="h-full w-full object-contain" controls autoplay loop
						></video>
					{:else if status === 'processing' || status === 'loading'}
						<div class="flex flex-col items-center gap-4 text-muted-foreground">
							<Loader2 class="h-8 w-8 animate-spin" />
							<p>Processing video task...</p>
							<p class="text-xs opacity-70">
								This typically takes 10-30 seconds depending on video length.
							</p>
						</div>
					{:else if status === 'error'}
						<div class="flex flex-col items-center gap-2 text-destructive">
							<p>Failed to load video result.</p>
						</div>
					{/if}
				</AspectRatio>
			</div>
		</div>

		<!-- Sidebar / Details -->
		<div class="flex w-full flex-col gap-4 lg:w-1/4">
			<div class="rounded-lg border p-4">
				<h3 class="mb-4 font-semibold">Details</h3>
				<div class="flex flex-col gap-2 text-sm text-muted-foreground">
					{#if task}
						<div class="flex justify-between">
							<span>Duration</span>
							<span class="font-medium text-foreground">{task.duration}</span>
						</div>
						<div class="flex justify-between">
							<span>Created</span>
							<span class="font-medium text-foreground">{task.createdAt}</span>
						</div>
						<div class="flex justify-between">
							<span>Format</span>
							<span class="font-medium text-foreground">{task.format}</span>
						</div>
					{:else}
						<div class="flex justify-between">
							<span>Task ID</span>
							<span class="font-mono text-xs text-foreground">{taskId}</span>
						</div>
						<div class="flex justify-between">
							<span>Status</span>
							<span class="font-medium text-foreground capitalize">{status}</span>
						</div>
					{/if}
				</div>
			</div>
		</div>
	</div>
</div>
