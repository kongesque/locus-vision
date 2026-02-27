<script lang="ts">
	import DrawingCanvas, { type Point, type Zone } from './drawing-canvas.svelte';
	import { onMount } from 'svelte';
	import Hls from 'hls.js';

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
	let videoRef: HTMLVideoElement | undefined = $state();
	let isLoading = $state(true);
	let error = $state<string | null>(null);
	let videoDims = $state<{
		width: number;
		height: number;
		naturalWidth: number;
		naturalHeight: number;
	} | null>(null);

	let hlsInstance: Hls | null = null;

	function isHlsUrl(src: string): boolean {
		return src.includes('.m3u8') || src.includes('manifest') || src.includes('hls');
	}

	function updateDims() {
		if (!videoRef || !containerRef) return;

		const { width: cw, height: ch } = containerRef.getBoundingClientRect();
		// Handle both <video> and <img> elements
		const isImg = videoRef instanceof HTMLImageElement;
		const nw = isImg ? (videoRef as unknown as HTMLImageElement).naturalWidth : videoRef.videoWidth;
		const nh = isImg
			? (videoRef as unknown as HTMLImageElement).naturalHeight
			: videoRef.videoHeight;

		if (nw === 0 || nh === 0) return;

		const containerRatio = cw / ch;
		const videoRatio = nw / nh;

		let displayW = cw;
		let displayH = ch;

		if (containerRatio > videoRatio) {
			displayW = ch * videoRatio;
		} else {
			displayH = cw / videoRatio;
		}

		videoDims = {
			width: displayW,
			height: displayH,
			naturalWidth: nw,
			naturalHeight: nh
		};
	}

	function initStream() {
		if (!videoRef || !url) return;

		// Clean up previous instance
		if (hlsInstance) {
			hlsInstance.destroy();
			hlsInstance = null;
		}

		if (isHlsUrl(url)) {
			// TODO: HLS proxy route disconnected
			// The backend proxy `/api/cameras/hls-proxy` was removed.
			//
			// Previous behavior:
			// const proxyUrl = `http://localhost:8000/api/cameras/hls-proxy?url=${encodeURIComponent(url)}`;
			const proxyUrl = '';

			if (Hls.isSupported()) {
				hlsInstance = new Hls({
					lowLatencyMode: true,
					enableWorker: true,
					backBufferLength: 0,
					maxBufferLength: 2,
					maxMaxBufferLength: 4,
					liveSyncDurationCount: 1,
					liveMaxLatencyDurationCount: 3,
					liveDurationInfinity: true,
					maxBufferSize: 0,
					startFragPrefetch: true
				});

				hlsInstance.loadSource(proxyUrl);
				hlsInstance.attachMedia(videoRef);

				hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
					isLoading = false;
					videoRef?.play().catch(() => {});
				});

				hlsInstance.on(Hls.Events.ERROR, (_event, data) => {
					if (data.fatal) {
						isLoading = false;
						error = `Stream error: ${data.details}`;
						console.error('HLS fatal error:', data);
					}
				});
			} else if (videoRef.canPlayType('application/vnd.apple.mpegurl')) {
				// Safari native HLS — also through proxy
				videoRef.src = proxyUrl;
				videoRef.addEventListener('loadedmetadata', () => {
					isLoading = false;
					videoRef?.play().catch(() => {});
				});
			} else {
				error = 'HLS not supported in this browser';
				isLoading = false;
			}
		} else {
			// Direct URL (RTSP won't work in browser, but HTTP streams might)
			// Fall back to MJPEG backend proxy for true RTSP
			// Because MJPEG is an image stream, it must be rendered in an <img> tag (in the template below),
			// not the <video> tag, so we just set isLoading to false and skip setting videoRef.src.
			isLoading = false;
		}
	}

	onMount(() => {
		initStream();

		const observer = new ResizeObserver(updateDims);
		if (containerRef) observer.observe(containerRef);

		return () => {
			observer.disconnect();
			if (hlsInstance) {
				hlsInstance.destroy();
				hlsInstance = null;
			}
		};
	});
</script>

<div
	bind:this={containerRef}
	class="relative flex h-full w-full items-center justify-center overflow-hidden rounded-lg bg-black"
>
	{#if error}
		<div class="flex flex-col items-center gap-3 p-4 text-center">
			<p class="text-sm text-red-500">{error}</p>
			<p class="max-w-[300px] text-xs break-all text-muted-foreground">{url}</p>
		</div>
	{:else}
		{#if isLoading}
			<div class="absolute z-20 flex flex-col items-center gap-2">
				<div
					class="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent"
				></div>
				<span class="text-sm text-muted-foreground">Connecting to stream...</span>
			</div>
		{/if}

		<!-- Native video playback — full FPS, hardware decoded (or MJPEG stream proxy) -->
		<!-- svelte-ignore a11y_media_has_caption -->
		{#if isHlsUrl(url)}
			<video
				bind:this={videoRef}
				class="pointer-events-none max-h-full max-w-full object-contain"
				autoplay
				playsinline
				muted
				onloadedmetadata={updateDims}
				onresize={updateDims}
			></video>
			<!-- TODO: MJPEG Proxy Route disconnected
			The backend proxy was removed at `/api/cameras/stream/${cameraId}`.
			
			Previous code:
			src={`http://localhost:8000/api/cameras/stream/${cameraId}`}
			-->
			<img
				bind:this={videoRef as any}
				src=""
				alt="Camera view (Disconnected)"
				class="pointer-events-none max-h-full max-w-full object-contain"
				onload={updateDims}
				onresize={updateDims}
				crossorigin="anonymous"
			/>
		{/if}

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
	{/if}
</div>
