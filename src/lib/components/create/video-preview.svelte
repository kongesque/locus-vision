<script lang="ts">
	import { useVideo } from '$lib/stores/video-store.svelte';
	import DrawingCanvas, { type Point, type Zone } from './drawing-canvas.svelte';
	import RtspSnapshotPreview from './rtsp-snapshot-preview.svelte';
	import { onMount } from 'svelte';

	interface Props {
		cameraId?: string;
		zones: Zone[];
		selectedZoneId: string | null;
		drawingMode: 'polygon' | 'line';
		onZoneCreated: (points: Point[]) => void;
		onZoneSelected: (id: string | null) => void;
		onZoneUpdated: (id: string, newPoints: Point[]) => void;
	}

	let {
		cameraId = '',
		zones,
		selectedZoneId,
		drawingMode,
		onZoneCreated,
		onZoneSelected,
		onZoneUpdated
	}: Props = $props();

	const videoState = useVideo();

	let videoRef: HTMLVideoElement | undefined = $state();
	let containerRef: HTMLDivElement | undefined = $state();
	let videoDims = $state<{
		width: number;
		height: number;
		naturalWidth: number;
		naturalHeight: number;
	} | null>(null);

	// Effect to handle video source
	$effect(() => {
		if (videoRef && videoState) {
			if (videoState.videoType === 'file' && videoState.videoUrl) {
				videoRef.srcObject = null;
				videoRef.src = videoState.videoUrl;
				videoRef.load();
			} else if (videoState.videoType === 'stream' && videoState.videoStream) {
				videoRef.src = '';
				videoRef.srcObject = videoState.videoStream;
				try {
					videoRef.play().catch((e) => console.log('Autoplay blocked:', e));
				} catch (e) {
					console.error('Error playing stream', e);
				}
			}
		}
	});

	function updateDims() {
		if (!videoRef) return;
		const video = videoRef;

		// Get the bounding rect of the VIDEO ELEMENT
		const { width: dw, height: dh } = video.getBoundingClientRect();

		// Get natural dimensions
		const nw = video.videoWidth;
		const nh = video.videoHeight;

		if (nw === 0 || nh === 0) return;

		// Calculate the actual displayed dimensions of the video content within the element
		const elementRatio = dw / dh;
		const videoRatio = nw / nh;

		let actualW = dw;
		let actualH = dh;

		if (elementRatio > videoRatio) {
			// Pillarbox: constrained by height
			actualW = dh * videoRatio;
		} else {
			// Letterbox: constrained by width
			actualH = dw / videoRatio;
		}

		videoDims = {
			width: actualW,
			height: actualH,
			naturalWidth: nw,
			naturalHeight: nh
		};
	}

	onMount(() => {
		const video = videoRef;
		if (video) {
			video.addEventListener('loadedmetadata', updateDims);
			video.addEventListener('resize', updateDims);
		}

		const observer = new ResizeObserver(updateDims);
		if (video) observer.observe(video);
		if (containerRef) observer.observe(containerRef);

		return () => {
			video?.removeEventListener('loadedmetadata', updateDims);
			video?.removeEventListener('resize', updateDims);
			observer.disconnect();
		};
	});
</script>

{#if videoState?.videoType === 'rtsp'}
	<RtspSnapshotPreview
		url={videoState.videoConfig?.url || videoState.videoUrl || ''}
		{cameraId}
		{zones}
		{selectedZoneId}
		{drawingMode}
		{onZoneCreated}
		{onZoneSelected}
		{onZoneUpdated}
	/>
{:else if !videoState?.videoUrl && !videoState?.videoStream}
	<div class="flex h-full w-full items-center justify-center bg-black text-muted-foreground">
		<p>No video selected</p>
	</div>
{:else}
	<div
		bind:this={containerRef}
		class="relative flex h-full w-full items-center justify-center overflow-hidden rounded-lg bg-black"
	>
		<!-- svelte-ignore a11y_media_has_caption -->
		<video
			bind:this={videoRef}
			class="pointer-events-none max-h-full max-w-full object-contain"
			autoplay
			loop
			muted
			playsinline
			crossorigin="anonymous"
		>
			{#if videoState?.videoType === 'file'}
				<source src={videoState.videoUrl || ''} type="video/mp4" />
			{/if}
			Your browser does not support the video tag.
		</video>

		<!-- Drawing Canvas Overlay -->
		{#if videoDims}
			<div
				class="absolute z-10 flex items-center justify-center"
				style="width: {videoDims.width}px; height: {videoDims.height}px;"
			>
				<DrawingCanvas
					width={videoDims.width}
					height={videoDims.height}
					videoWidth={videoDims.naturalWidth}
					videoHeight={videoDims.naturalHeight}
					{zones}
					{selectedZoneId}
					{drawingMode}
					{onZoneCreated}
					{onZoneSelected}
					{onZoneUpdated}
				/>
			</div>
		{/if}
	</div>
{/if}
