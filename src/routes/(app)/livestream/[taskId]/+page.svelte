<script lang="ts">
	import { page } from '$app/stores';
	import { AspectRatio } from '$lib/components/ui/aspect-ratio';
	import { videoStore } from '$lib/stores/video.svelte';

	const taskId = $derived($page.params.taskId);

	let cameraName = $state('Loading...');
	let cameraStatus = $state('connecting');
	let errorMsg = $state<string | null>(null);
	let zones = $state<any[]>([]);
	let trackCount = $state(0);

	// Action for Video Element
	function videoAction(node: HTMLVideoElement) {
		let isDestroyed = false;

		const initVideo = async () => {
			try {
				const res = await fetch(`http://localhost:8000/api/cameras/${taskId}`);
				if (!res.ok) throw new Error('Camera not found');

				const camera = await res.json();
				cameraName = camera.name;
				zones = camera.zones || [];

				if (camera.type === 'webcam') {
					if (videoStore.videoStream) {
						node.srcObject = videoStore.videoStream;
						cameraStatus = 'live';
					} else {
						// Svelte store was reset (e.g., user refreshed the page)
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
							console.error('Failed to restore webcam stream:', err);
							errorMsg = 'Webcam access denied or unavailable.';
							cameraStatus = 'error';
						}
					}
				} else if (camera.type === 'rtsp') {
					cameraStatus = 'live (rtsp simulation)';
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
			}
		};
	}

	// Action for Canvas Overlay (WebSocket)
	function overlayAction(node: HTMLCanvasElement) {
		const ws = new WebSocket(`ws://localhost:8000/api/cameras/${taskId}/ws`);
		let resizeObserver: ResizeObserver | null = null;

		// Ensure canvas size matches its CSS display size
		function resizeCanvas() {
			if (node.parentElement) {
				node.width = node.parentElement.clientWidth;
				node.height = node.parentElement.clientHeight;
			}
		}

		resizeObserver = new ResizeObserver(resizeCanvas);
		if (node.parentElement) resizeObserver.observe(node.parentElement);
		resizeCanvas();

		ws.onopen = () => console.log('Analytics WebSocket connected');

		let videoRes = { w: 1, h: 1 };

		ws.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data);
				if (data.resolution) {
					videoRes = data.resolution;
				}
				if (data.boxes) {
					drawOverlay(node, data.boxes, videoRes);
					trackCount = data.boxes.length;
				}
			} catch (e) {
				console.error('Error parsing websocket message', e);
			}
		};

		ws.onclose = () => console.log('Analytics WebSocket disconnected');

		return {
			destroy() {
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

		// Calculate scale factors between the raw video stream and the HTML canvas rendering size
		// The aspect ratio is preserved by object-contain, so the video might not fill the entire canvas!
		// But in our setup, AspectRatio component is strictly enforcing 16:9, and we assume video matches it.
		// A more robust way is calculating the letterboxing offsets, but for now simple stretch works if 16:9.
		const scaleX = canvas.width / videoRes.w;
		const scaleY = canvas.height / videoRes.h;

		// Draw configured zones
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

		// Draw bounding boxes
		boxes.forEach((box) => {
			ctx.strokeStyle = '#ff0000';
			ctx.lineWidth = 2;

			const scaledX = box.x * scaleX;
			const scaledY = box.y * scaleY;
			const scaledW = box.w * scaleX;
			const scaledH = box.h * scaleY;

			ctx.strokeRect(scaledX, scaledY, scaledW, scaledH);

			if (box.class !== undefined) {
				ctx.fillStyle = '#ff0000';
				ctx.fillRect(scaledX, scaledY - 20, Math.max(scaledW, 50), 20);
				ctx.fillStyle = '#ffffff';
				ctx.font = '12px Arial';
				ctx.fillText(`ID: ${box.id} C: ${box.class}`, scaledX + 5, scaledY - 5);
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
					<video use:videoAction class="h-full w-full object-contain" autoplay playsinline muted
					></video>

					<canvas use:overlayAction class="pointer-events-none absolute top-0 left-0 h-full w-full"
					></canvas>
				</AspectRatio>
			</div>

			<div class="grid grid-cols-3 gap-4">
				<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
					<div class="text-sm font-semibold text-muted-foreground">Detection Model</div>
					<div class="mt-1 text-lg tracking-tight">YOLO11n (Live)</div>
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
