<script lang="ts">
	import { onMount, type Snippet } from 'svelte';
	import PageTitle from '$lib/components/page-title-2.svelte';
	import AddCamera from '$lib/components/livestream/add-camera.svelte';
	import LiveCard from './live-card.svelte';
	import LivestreamControls from './livestream-controls.svelte';

	interface Camera {
		id: string;
		name: string;
		status: string;
		thumbnail?: string;
	}

	let { initialGridCols = 3 }: { initialGridCols?: number } = $props();

	// svelte-ignore state_referenced_locally
	let gridCols = $state(initialGridCols);

	$effect(() => {
		gridCols = initialGridCols;
	});
	let isFullscreen = $state(false);
	let cameras: Camera[] = $state([]);
	let gridContainer: HTMLDivElement | null = $state(null);

	onMount(() => {
		fetch('/data/events.json')
			.then((res) => res.json())
			.then((data) => {
				if (data.cameras) {
					cameras = data.cameras;
				}
			})
			.catch((err) => console.error('Failed to load cameras:', err));

		const handleFullscreenChange = () => {
			isFullscreen = !!document.fullscreenElement;
		};

		document.addEventListener('fullscreenchange', handleFullscreenChange);
		return () => {
			document.removeEventListener('fullscreenchange', handleFullscreenChange);
		};
	});

	const toggleFullscreen = () => {
		if (!document.fullscreenElement) {
			gridContainer?.requestFullscreen().catch((err) => {
				console.error(`Error attempting to enable full-screen mode: ${err.message} (${err.name})`);
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
		bind:this={gridContainer}
		class={`relative flex flex-1 flex-col ${isFullscreen ? 'fixed top-0 left-0 z-50 h-screen w-screen overflow-y-auto bg-background' : ''}`}
	>
		<div
			class={`grid auto-rows-min grid-cols-1 gap-2 md:[grid-template-columns:repeat(var(--cols),minmax(0,1fr))] ${isFullscreen ? 'w-full p-4' : ''}`}
			style="--cols: {gridCols}"
		>
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

		<LivestreamControls
			{gridCols}
			setGridCols={(cols) => (gridCols = cols)}
			{isFullscreen}
			{toggleFullscreen}
		/>
	</div>
</div>
