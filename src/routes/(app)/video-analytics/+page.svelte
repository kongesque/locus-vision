<script lang="ts">
	import PageTitle2 from '$lib/components/page-title-2.svelte';
	import { API_URL } from '$lib/api';
	import UploadArea from '$lib/components/video-analytics/upload-area.svelte';
	import SearchInput from '$lib/components/video-analytics/search-input.svelte';
	import VideoCard from '$lib/components/video-analytics/video-card.svelte';
	import QueueStatus from '$lib/components/video-analytics/queue-status.svelte';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { AlertTriangle, Loader2, Trash2 } from '@lucide/svelte';
	import { onMount, onDestroy, untrack } from 'svelte';

	let { data } = $props();
	let history = $state<any[]>(untrack(() => data.history || []));
	let searchQuery = $state('');
	let refreshTimer: ReturnType<typeof setInterval>;

	// Delete dialog state
	let isDeleteDialogOpen = $state(false);
	let taskToDelete: any = $state(null);
	let isDeleting = $state(false);
	let deleteError = $state('');

	let filteredHistory = $derived(
		history.filter((item: any) =>
			((item.name || item.filename) || item.id).toLowerCase().includes(searchQuery.toLowerCase())
		)
	);

	async function refreshHistory() {
		try {
			const res = await fetch(`${API_URL}/api/video/history`);
			if (res.ok) {
				history = await res.json();
			}
		} catch {
			// silent
		}
	}

	onMount(() => {
		// Auto-refresh history every 5s to pick up completed tasks
		refreshTimer = setInterval(refreshHistory, 5000);
	});

	onDestroy(() => {
		if (refreshTimer) clearInterval(refreshTimer);
	});

	function openDeleteDialog(task: any) {
		taskToDelete = task;
		deleteError = '';
		isDeleteDialogOpen = true;
	}

	async function deleteTask() {
		if (!taskToDelete) return;

		isDeleting = true;
		deleteError = '';

		try {
			const res = await fetch(`${API_URL}/api/video/${taskToDelete.id}`, {
				method: 'DELETE'
			});

			if (res.ok) {
				// Remove from local state
				history = history.filter((item) => item.id !== taskToDelete.id);
				isDeleteDialogOpen = false;
				taskToDelete = null;
			} else {
				const data = await res.json();
				deleteError = data.detail || 'Failed to delete task';
			}
		} catch (e) {
			deleteError = 'Network error. Please try again.';
		} finally {
			isDeleting = false;
		}
	}
</script>

<svelte:head>
	<title>Video Analytics · Locus</title>
</svelte:head>

<div class="flex flex-1 flex-col gap-4 p-4">
	<PageTitle2 />
	<UploadArea />
	<QueueStatus />

	<div class="mt-4 flex flex-col gap-4">
		<SearchInput bind:value={searchQuery} />

		{#if filteredHistory.length > 0}
			<div class="grid grid-cols-1 gap-4 md:grid-cols-4">
				{#each filteredHistory as item (item.id)}
					<VideoCard
						taskId={item.id}
						name={item.name || item.filename}
						duration={item.duration || '--:--'}
						createdAt={new Date(item.created_at).toLocaleString()}
						format={item.format || 'mp4'}
						status={item.status}
						progress={item.progress || 0}
						thumbnail={`${API_URL}/api/video/${item.id}/thumbnail`}
						onDelete={() => openDeleteDialog(item)}
					/>
				{/each}
			</div>
		{:else if history.length === 0}
			<div
				class="col-span-full flex flex-col items-center justify-center rounded-xl border border-dashed p-12 text-center"
			>
				<p class="text-sm text-muted-foreground">No videos processed yet.</p>
				<p class="mt-1 text-xs text-muted-foreground">Upload a video above to get started.</p>
			</div>
		{:else}
			<div class="flex h-24 items-center justify-center">
				<span class="text-muted-foreground">No results found.</span>
			</div>
		{/if}
	</div>
</div>

<!-- Delete Confirmation Dialog -->
<Dialog.Root bind:open={isDeleteDialogOpen}>
	<Dialog.Content class="sm:max-w-[400px]">
		<Dialog.Header>
			<Dialog.Title class="flex items-center gap-2 text-red-600">
				<AlertTriangle class="size-5" />
				Delete Task
			</Dialog.Title>
			<Dialog.Description>
				Are you sure you want to delete <strong>{(taskToDelete?.name || taskToDelete?.filename) || 'this task'}</strong>? This
				action cannot be undone.
			</Dialog.Description>
		</Dialog.Header>
		{#if deleteError}
			<div class="text-sm text-red-600">{deleteError}</div>
		{/if}
		<Dialog.Footer class="gap-2 sm:justify-end">
			<Button variant="outline" onclick={() => (isDeleteDialogOpen = false)} class="cursor-pointer">Cancel</Button>
			<Button variant="destructive" onclick={deleteTask} disabled={isDeleting} class="cursor-pointer">
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
