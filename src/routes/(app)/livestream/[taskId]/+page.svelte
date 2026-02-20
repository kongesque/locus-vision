<script lang="ts">
	import { page } from '$app/stores';
	import { AspectRatio } from '$lib/components/ui/aspect-ratio';
	import { videoStore } from '$lib/stores/video.svelte';
	import Hls from 'hls.js';

	const taskId = $derived($page.params.taskId);

	let cameraName = $state('Loading...');
	let cameraStatus = $state('connecting');
	let cameraType = $state<'webcam' | 'rtsp'>('webcam');
	let cameraUrl = $state('');
	let modelName = $state('yolo11n');
	let errorMsg = $state<string | null>(null);
	let zones = $state<any[]>([]);
	let trackCount = $state(0);

	function isHlsUrl(src: string): boolean {
		return src.includes('.m3u8') || src.includes('manifest') || src.includes('hls');
	}

	// Action for initializing the camera feed
	function videoAction(node: HTMLVideoElement) {
		let isDestroyed = false;
		let hlsInstance: Hls | null = null;

		const initVideo = async () => {
			try {
				const res = await fetch(`http://localhost:8000/api/cameras/${taskId}`);
				if (!res.ok) throw new Error('Camera not found');

				const camera = await res.json();
				cameraName = camera.name;
				cameraType = camera.type;
				cameraUrl = camera.url || '';
				modelName = camera.model_name || 'yolo11n';
				zones = camera.zones || [];

				if (camera.type === 'webcam') {
					if (videoStore.videoStream) {
						node.srcObject = videoStore.videoStream;
						cameraStatus = 'live';
					} else {
						try {
							const stream = await navigator.mediaDevices.getUserMedia({
								video:
									camera.device_id && camera.device_id !== 'default'
										? { deviceId: { exact: camera.device_id } }
										: true
							});
							videoStore.setVideoStream(stream);
							videoStore.setVideoType('stream');
							node.srcObject = stream;
							cameraStatus = 'live';
						} catch (err) {
							console.error('Failed to restore webcam:', err);
							errorMsg = 'Webcam access denied or unavailable.';
							cameraStatus = 'error';
						}
					}
				} else if (camera.type === 'rtsp' && camera.url) {
					// Play HLS/RTSP stream in the <video> element
					if (isHlsUrl(camera.url)) {
						const proxyUrl = `http://localhost:8000/api/cameras/hls-proxy?url=${encodeURIComponent(camera.url)}`;

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
							hlsInstance.attachMedia(node);
							hlsInstance.on(Hls.Events.MANIFEST_PARSED, () => {
								cameraStatus = 'live';
								node.play().catch(() => {});
							});
							hlsInstance.on(Hls.Events.ERROR, (_event, data) => {
								if (data.fatal) {
									console.error('HLS error:', data);
									errorMsg = `Stream error: ${data.details}`;
									cameraStatus = 'error';
								}
							});
						} else if (node.canPlayType('application/vnd.apple.mpegurl')) {
							node.src = proxyUrl;
							node.addEventListener('loadedmetadata', () => {
								cameraStatus = 'live';
								node.play().catch(() => {});
							});
						}
					} else {
						// Non-HLS RTSP — can't play directly in browser
						cameraStatus = 'live';
					}
				}
			} catch (err) {
				if (isDestroyed) return;
				console.error(err);
				errorMsg = err instanceof Error ? err.message : String(err);
				cameraStatus = 'error';
			}
		};

		initVideo();

		return {
			destroy() {
				isDestroyed = true;
				if (hlsInstance) {
					hlsInstance.destroy();
					hlsInstance = null;
				}
			}
		};
	}

	// Action for Canvas Overlay (WebSocket + frame relay for webcam / listen-only for RTSP)
	function overlayAction(node: HTMLCanvasElement) {
		const ws = new WebSocket(`ws://localhost:8000/api/cameras/${taskId}/ws`);
		let resizeObserver: ResizeObserver | null = null;
		let captureInterval: ReturnType<typeof setInterval> | null = null;
		let videoEl: HTMLVideoElement | null = null;

		// Hidden offscreen canvas for webcam frame capture
		const captureCanvas = document.createElement('canvas');
		const captureCtx = captureCanvas.getContext('2d');

		function resizeCanvas() {
			if (node.parentElement) {
				node.width = node.parentElement.clientWidth;
				node.height = node.parentElement.clientHeight;
			}
		}

		resizeObserver = new ResizeObserver(resizeCanvas);
		if (node.parentElement) resizeObserver.observe(node.parentElement);
		resizeCanvas();

		let videoRes = { w: 1, h: 1 };

		ws.onopen = () => {
			console.log('Analytics WebSocket connected');

			// Only send frames if this is a webcam camera
			if (cameraType === 'webcam') {
				videoEl = node.parentElement?.querySelector('video') ?? null;
				if (!videoEl) {
					console.warn('No <video> element found for frame capture');
					return;
				}

				captureInterval = setInterval(() => {
					if (!videoEl || videoEl.readyState < 2 || ws.readyState !== WebSocket.OPEN) return;

					captureCanvas.width = videoEl.videoWidth || 640;
					captureCanvas.height = videoEl.videoHeight || 480;
					captureCtx?.drawImage(videoEl, 0, 0, captureCanvas.width, captureCanvas.height);

					captureCanvas.toBlob(
						(blob) => {
							if (blob && ws.readyState === WebSocket.OPEN) {
								blob.arrayBuffer().then((buf) => ws.send(buf));
							}
						},
						'image/jpeg',
						0.6
					);
				}, 125); // ~8 FPS
			}
		};

		ws.onmessage = (event) => {
			try {
				const raw = typeof event.data === 'string' ? event.data : '';
				const data = JSON.parse(raw);
				if (data.resolution) videoRes = data.resolution;
				if (data.boxes) {
					drawOverlay(node, data.boxes, videoRes);
					trackCount = data.boxes.length;
				}
			} catch (e) {
				console.error('WS parse error', e);
			}
		};

		ws.onclose = () => console.log('Analytics WebSocket disconnected');

		return {
			destroy() {
				if (captureInterval) clearInterval(captureInterval);
				ws.close();
				if (resizeObserver) resizeObserver.disconnect();
			}
		};
	}

	function drawOverlay(
		canvas: HTMLCanvasElement,
		boxes: any[],
		videoRes: { w: number; h: number }
	) {
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		ctx.clearRect(0, 0, canvas.width, canvas.height);

		const scaleX = canvas.width / videoRes.w;
		const scaleY = canvas.height / videoRes.h;

		zones.forEach((zone) => {
			if (!zone.points || zone.points.length < 2) return;

			ctx.beginPath();
			ctx.strokeStyle = zone.color || '#00ff00';
			ctx.lineWidth = 2;
			ctx.setLineDash([5, 5]);

			const firstPt = zone.points[0];
			ctx.moveTo(firstPt.x * scaleX, firstPt.y * scaleY);

			for (let i = 1; i < zone.points.length; i++) {
				ctx.lineTo(zone.points[i].x * scaleX, zone.points[i].y * scaleY);
			}
			if (zone.type === 'polygon') ctx.closePath();
			ctx.stroke();
			ctx.setLineDash([]);
		});

		boxes.forEach((box) => {
			ctx.strokeStyle = '#ff0000';
			ctx.lineWidth = 2;

			const scaledX = box.x * scaleX;
			const scaledY = box.y * scaleY;
			const scaledW = box.w * scaleX;
			const scaledH = box.h * scaleY;

			ctx.strokeRect(scaledX, scaledY, scaledW, scaledH);

			if (box.label) {
				ctx.fillStyle = 'rgba(255, 0, 0, 0.8)';
				const labelText = `${box.label} #${box.id}`;
				const textWidth = ctx.measureText(labelText).width + 10;
				ctx.fillRect(scaledX, scaledY - 22, textWidth, 22);
				ctx.fillStyle = '#ffffff';
				ctx.font = 'bold 13px Inter, Arial, sans-serif';
				ctx.fillText(labelText, scaledX + 5, scaledY - 6);
			}
		});
	}
</script>

<div class="flex flex-1 flex-col gap-4 p-4">
	<div class="mb-2 flex items-center justify-between">
		<h1 class="text-2xl font-bold">{cameraName}</h1>
		<div class="flex items-center gap-2">
			<span class="relative flex h-3 w-3">
				{#if cameraStatus === 'live' || cameraStatus.includes('live')}
					<span
						class="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75"
					></span>
					<span class="relative inline-flex h-3 w-3 rounded-full bg-green-500"></span>
				{:else if cameraStatus === 'connecting'}
					<span class="relative inline-flex h-3 w-3 rounded-full bg-yellow-500"></span>
				{:else}
					<span class="relative inline-flex h-3 w-3 rounded-full bg-red-500"></span>
				{/if}
			</span>
			<span class="text-sm font-medium text-muted-foreground capitalize">{cameraStatus}</span>
		</div>
	</div>

	{#if errorMsg}
		<div class="rounded-md border border-red-500/20 bg-red-500/10 p-4 text-red-500">
			{errorMsg}
		</div>
	{/if}

	<div class="flex flex-1 flex-row gap-4">
		<div class="mx-auto flex w-full max-w-5xl flex-col gap-4">
			<div class="relative overflow-hidden rounded-lg border bg-black shadow-lg">
				<AspectRatio ratio={16 / 9} class="group relative max-h-[80vh]">
					<!-- Single <video> element for both webcam and RTSP/HLS -->
					<!-- svelte-ignore a11y_media_has_caption -->
					<video use:videoAction class="h-full w-full object-contain" autoplay playsinline muted
					></video>

					<canvas use:overlayAction class="pointer-events-none absolute top-0 left-0 h-full w-full"
					></canvas>
				</AspectRatio>
			</div>

			<div class="grid grid-cols-3 gap-4">
				<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
					<div class="text-sm font-semibold text-muted-foreground">Detection Model</div>
					<div class="mt-1 text-lg tracking-tight">{modelName} (Live)</div>
				</div>
				<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
					<div class="text-sm font-semibold text-muted-foreground">Active Zones</div>
					<div class="mt-1 text-lg tracking-tight">{zones.length}</div>
				</div>
				<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
					<div class="text-sm font-semibold text-muted-foreground">Objects Tracked</div>
					<div class="mt-1 text-lg tracking-tight">{trackCount}</div>
				</div>
			</div>
		</div>
	</div>
</div>
