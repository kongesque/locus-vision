<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { apiFetch } from '$lib/api';
	import { Loader2, Clock, Layers } from '@lucide/svelte';

	interface QueueTask {
		task_id: string;
		filename: string;
		progress?: number;
	}

	interface QueueStatus {
		queue_length: number;
		processing: QueueTask | null;
		pending: QueueTask[];
	}

	let status = $state<QueueStatus | null>(null);
	let pollTimer: ReturnType<typeof setInterval>;

	async function fetchStatus() {
		try {
			const res = await apiFetch('/api/video/queue/status');
			if (res.ok) {
				status = await res.json();
			}
		} catch {
			// Backend not reachable — silent
		}
	}

	onMount(() => {
		fetchStatus();
		pollTimer = setInterval(fetchStatus, 3000);
	});

	onDestroy(() => {
		if (pollTimer) clearInterval(pollTimer);
	});

	let isVisible = $derived(status && status.queue_length > 0);
</script>

{#if isVisible && status}
	<div class="overflow-hidden rounded-lg border border-blue-500/20 bg-blue-500/5">
		<!-- Header -->
		<div class="flex items-center gap-2 border-b border-blue-500/10 px-4 py-3">
			<Layers class="h-4 w-4 text-blue-400" />
			<span class="text-sm font-semibold text-blue-400">Processing Queue</span>
			<span
				class="ml-auto rounded-full bg-blue-500/20 px-2 py-0.5 text-xs font-medium text-blue-300"
			>
				{status.queue_length} task{status.queue_length !== 1 ? 's' : ''}
			</span>
		</div>

		<div class="flex flex-col gap-0 divide-y divide-border/50">
			<!-- Currently Processing -->
			{#if status.processing}
				<div class="flex items-center gap-3 px-4 py-3">
					<Loader2 class="h-4 w-4 shrink-0 animate-spin text-blue-400" />
					<div class="flex min-w-0 flex-1 flex-col gap-1.5">
						<div class="flex items-center justify-between">
							<span class="truncate text-sm font-medium">
								{status.processing.filename}
							</span>
							<span class="shrink-0 font-mono text-xs text-blue-400">
								{status.processing.progress ?? 0}%
							</span>
						</div>
						<div class="h-1.5 w-full overflow-hidden rounded-full bg-muted">
							<div
								class="h-full rounded-full bg-blue-500 transition-all duration-500 ease-out"
								style="width: {status.processing.progress ?? 0}%"
							></div>
						</div>
					</div>
				</div>
			{/if}

			<!-- Pending Tasks -->
			{#each status.pending as task, i (task.task_id)}
				<div class="flex items-center gap-3 px-4 py-2.5 opacity-60">
					<Clock class="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
					<span class="truncate text-sm text-muted-foreground">
						{task.filename}
					</span>
					<span
						class="ml-auto shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
					>
						#{i + 1} in queue
					</span>
				</div>
			{/each}
		</div>
	</div>
{/if}
