<script lang="ts">
	import { onMount } from 'svelte';
	import { API_URL } from '$lib/api';
	import PageTitle from '$lib/components/page-title-2.svelte';
	import AddCamera from '$lib/components/livestream/add-camera.svelte';
	import LiveCard from './live-card.svelte';
	import LivestreamControls from './livestream-controls.svelte';

	interface Camera {
		id: string;
		name: string;
		status: 'active' | 'draft' | 'offline' | 'connecting';
		thumbnail?: string;
	}

	let props: { initialGridCols?: number } = $props();

	let gridCols = $state(props.initialGridCols ?? 3);

	let isFullscreen = $state(false);
	let cameras: Camera[] = $state([]);
	let gridContainer: HTMLDivElement | null = $state(null);
	let refreshTimer: ReturnType<typeof setInterval>;

	async function fetchCameras() {
		try {
			const res = await fetch(`${API_URL}/api/cameras`);
			if (res.ok) {
				const allCameras = await res.json();
				// Only show cameras with 'active' status (configured and ready to use)
				cameras = allCameras.filter((cam: Camera) => cam.status === 'active');
			}
		} catch {
			// silent — backend might be down
		}
	}

	// Container action to manage fullscreen requests
	function fullscreenAction(node: HTMLDivElement) {
		gridContainer = node;

		const handleFullscreenChange = () => {
			isFullscreen = !!document.fullscreenElement;
		};

		document.addEventListener('fullscreenchange', handleFullscreenChange);
		return {
			destroy() {
				gridContainer = null;
				document.removeEventListener('fullscreenchange', handleFullscreenChange);
			}
		};
	}

	onMount(() => {
		fetchCameras();
		refreshTimer = setInterval(fetchCameras, 5000);
	});

	import { onDestroy } from 'svelte';
	onDestroy(() => {
		if (refreshTimer) clearInterval(refreshTimer);
	});

	const toggleFullscreen = () => {
		if (!document.fullscreenElement) {
			gridContainer?.requestFullscreen().catch((err) => {
				console.error(`Error attempting to enable full-screen mode: ${err.message}`);
			});
		} else {
			document.exitFullscreen();
		}
	};

	$effect(() => {
		document.cookie = `livestream_cols=${gridCols}; path=/; max-age=${60 * 60 * 24 * 365}`;
	});

	let cardSize = $derived(gridCols >= 5 ? 'sm' : gridCols >= 3 ? 'md' : 'lg') as 'sm' | 'md' | 'lg';
</script>

<div class="relative flex flex-1 flex-col gap-4 p-4">
	<div class="flex items-center justify-between">
		<PageTitle />
		<AddCamera />
	</div>

	<div
		use:fullscreenAction
		class={`relative flex flex-1 flex-col ${isFullscreen ? 'fixed top-0 left-0 z-50 h-screen w-screen overflow-y-auto bg-background' : ''}`}
	>
		<div
			class={`grid auto-rows-min grid-cols-1 gap-4 md:[grid-template-columns:repeat(var(--cols),minmax(0,1fr))] ${isFullscreen ? 'w-full p-4' : ''}`}
			style="--cols: {gridCols}"
		>
			{#if cameras.length === 0}
				<div
					class="col-span-full flex flex-col items-center justify-center rounded-xl border border-dashed p-12 text-center"
				>
					<p class="text-sm text-muted-foreground">No cameras configured yet.</p>
					<p class="mt-1 text-xs text-muted-foreground">Click "Add Camera" to get started.</p>
				</div>
			{/if}

			{#each cameras as camera (camera.id)}
				<LiveCard
					cameraId={camera.id}
					cameraName={camera.name}
					status={camera.status as 'live' | 'offline' | 'connecting'}
					thumbnail={camera.thumbnail}
					size={cardSize}
				/>
			{/each}
		</div>

		{#if cameras.length > 0}
			<LivestreamControls
				{gridCols}
				setGridCols={(cols) => (gridCols = cols)}
				{isFullscreen}
				{toggleFullscreen}
			/>
		{/if}
	</div>
</div>
