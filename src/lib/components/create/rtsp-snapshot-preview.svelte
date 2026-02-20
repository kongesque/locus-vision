<script lang="ts">
	import DrawingCanvas, { type Point, type Zone } from './drawing-canvas.svelte';
	import { onMount } from 'svelte';

	interface Props {
		url: string;
		cameraId: string;
		zones: Zone[];
		selectedZoneId: string | null;
		drawingMode: 'polygon' | 'line';
		onZoneCreated: (points: Point[]) => void;
		onZoneSelected: (id: string | null) => void;
		onZoneUpdated: (id: string, newPoints: Point[]) => void;
	}

	let {
		url,
		cameraId,
		zones,
		selectedZoneId,
		drawingMode,
		onZoneCreated,
		onZoneSelected,
		onZoneUpdated
	}: Props = $props();

	let containerRef: HTMLDivElement | undefined = $state();
	let imgRef: HTMLImageElement | undefined = $state();
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let imageDims = $state<{
		width: number;
		height: number;
		naturalWidth: number;
		naturalHeight: number;
	} | null>(null);

	// MJPEG stream URL — the browser's <img> tag handles multipart/x-mixed-replace natively
	const streamUrl = $derived(`http://localhost:8000/api/cameras/stream/${cameraId}`);

	function updateDims() {
		if (!imgRef || !containerRef) return;

		const { width: cw, height: ch } = containerRef.getBoundingClientRect();
		const nw = imgRef.naturalWidth;
		const nh = imgRef.naturalHeight;

		if (nw === 0 || nh === 0) return;

		const containerRatio = cw / ch;
		const imageRatio = nw / nh;

		let displayW = cw;
		let displayH = ch;

		if (containerRatio > imageRatio) {
			displayW = ch * imageRatio;
		} else {
			displayH = cw / imageRatio;
		}

		imageDims = {
			width: displayW,
			height: displayH,
			naturalWidth: nw,
			naturalHeight: nh
		};
	}

	function handleLoad() {
		isLoading = false;
		error = null;
		updateDims();
	}

	function handleError() {
		isLoading = false;
		error = 'Could not connect to stream. Check the URL and backend.';
	}

	onMount(() => {
		const observer = new ResizeObserver(updateDims);
		if (containerRef) observer.observe(containerRef);

		return () => observer.disconnect();
	});
</script>

<div
	bind:this={containerRef}
	class="relative flex h-full w-full items-center justify-center overflow-hidden rounded-lg bg-black"
>
	{#if error}
		<div class="flex flex-col items-center gap-3 text-center">
			<p class="text-sm text-red-500">{error}</p>
			<p class="max-w-[300px] text-xs break-all text-muted-foreground">{url}</p>
		</div>
	{:else}
		{#if isLoading}
			<div class="absolute z-20 animate-pulse text-sm text-muted-foreground">
				Connecting to live stream...
			</div>
		{/if}

		<!-- MJPEG live stream: the browser natively handles multipart/x-mixed-replace as a live updating image -->
		<img
			bind:this={imgRef}
			src={streamUrl}
			alt="Live RTSP stream"
			class="pointer-events-none max-h-full max-w-full object-contain"
			onload={handleLoad}
			onerror={handleError}
		/>

		<!-- Drawing Canvas Overlay -->
		{#if imageDims}
			<div
				class="absolute z-10 flex items-center justify-center"
				style="width: {imageDims.width}px; height: {imageDims.height}px;"
			>
				<DrawingCanvas
					width={imageDims.width}
					height={imageDims.height}
					videoWidth={imageDims.naturalWidth}
					videoHeight={imageDims.naturalHeight}
					{zones}
					{selectedZoneId}
					{drawingMode}
					{onZoneCreated}
					{onZoneSelected}
					{onZoneUpdated}
				/>
			</div>
		{/if}
	{/if}
</div>
