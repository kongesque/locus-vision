<script lang="ts">
	import { page } from '$app/stores';
	import { AspectRatio } from '$lib/components/ui/aspect-ratio';
	import { videoStore } from '$lib/stores/video.svelte';

	const taskId = $derived($page.params.taskId);

	let cameraName = $state('Loading...');
	let cameraStatus = $state('connecting');
	let cameraType = $state<'webcam' | 'rtsp'>('webcam');
	let cameraUrl = $state('');
	let modelName = $state('yolo11n');
	let errorMsg = $state<string | null>(null);
	let zones = $state<any[]>([]);
	let trackCount = $state(0);
	let zoneCounts = $state<Record<string, number>>({});

	// Activity Log to show history of detections entering zones
	let activityLogs = $state<{ time: string; message: string; id: string }[]>([]);

	function addActivityLog(message: string) {
		const now = new Date();
		const timeStr = now.toLocaleTimeString([], {
			hour12: false,
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit'
		});
		activityLogs = [
			{ time: timeStr, message, id: Math.random().toString() },
			...activityLogs
		].slice(0, 50); // Keep last 50
	}

	// Action for initializing the camera feed
	function videoAction(node: HTMLVideoElement) {
		let isDestroyed = false;

		const initVideo = async () => {
			try {
				// TODO: Fetch single camera info from backend disconnected
				// The backend fetching API for individual cameras has been deleted.
				//
				// Previous behavior:
				// const res = await fetch(`http://localhost:8000/api/cameras/${taskId}`);
				throw new Error('Single camera detail disconnected: see source code');

				if (cameraType === 'webcam') {
					if (videoStore.videoStream) {
						node.srcObject = videoStore.videoStream;
						cameraStatus = 'live';
					} else {
						try {
							const stream = await navigator.mediaDevices.getUserMedia({
								video: true
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
				} else if (cameraType === 'rtsp' && cameraUrl) {
					// RTSP relies on MJPEG route.
					cameraStatus = 'live';
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

	// Action for Canvas Overlay (WebSocket + frame relay for webcam / listen-only for RTSP)
	function overlayAction(node: HTMLCanvasElement) {
		// TODO: Analytics WebSocket disconnected
		// The backend websocket `ws://localhost:8000/api/cameras/${taskId}/ws` was removed.
		// WebSocket object creation string should simply use a no-op endpoint or be entirely removed.
		const ws = {
			onopen: () => {},
			onmessage: (e: any) => {},
			onclose: () => {},
			close: () => {},
			readyState: 0,
			send: (b: any) => {}
		} as unknown as WebSocket;
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

			videoEl = node.parentElement?.querySelector('video') ?? null;
			let imgEl = node.parentElement?.querySelector('img') ?? null;
			if (!videoEl && !imgEl) {
				console.warn('No <video> or <img> element found for frame capture');
			}

			captureInterval = setInterval(() => {
				// Only send frames for webcam. RTSP is processed continuously in the background backend.
				if (cameraType !== 'webcam') return;

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
		};

		ws.onmessage = (event) => {
			try {
				const raw = typeof event.data === 'string' ? event.data : '';
				const data = JSON.parse(raw);
				if (data.resolution) videoRes = data.resolution;

				// Re-query in case it changed between webcam/rtsp
				videoEl = node.parentElement?.querySelector('video') ?? null;
				let currentImgEl = node.parentElement?.querySelector('img') ?? null;

				if (data.boxes) {
					drawOverlay(node, videoEl || currentImgEl, data.boxes, videoRes);
				}
				// Use the backend's zone-aware unique count
				if (data.count !== undefined) {
					if (trackCount !== data.count && data.count > 0) {
						// Only log if it's an overall new object (if we don't have zone specifics)
						// But wait, it's better to log zone-specific increases!
					}
					trackCount = data.count;
				}
				if (data.zone_counts) {
					// Check for increases to trigger activity logs
					for (const [zId, newCount] of Object.entries(data.zone_counts)) {
						const oldCount = zoneCounts[zId] || 0;
						if ((newCount as number) > oldCount) {
							// Find the zone name for better UI
							const zoneName = zones.find((z) => z.id === zId)?.id || zId;
							const shortName = zoneName.length > 8 ? `Zone ${zoneName.slice(0, 4)}` : zoneName;
							addActivityLog(`Occupancy increased in ${shortName}`);
						}
					}
					zoneCounts = data.zone_counts;
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
		videoEl: HTMLVideoElement | HTMLImageElement | null,
		boxes: any[],
		videoRes: { w: number; h: number }
	) {
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		ctx.clearRect(0, 0, canvas.width, canvas.height);

		if (!videoRes || videoRes.w === 0 || videoRes.h === 0 || !videoEl) return;

		// videoEl natively reports its actual visual dimensions on-screen after object-contain!
		const renderW = videoEl.clientWidth;
		const renderH = videoEl.clientHeight;

		// The canvas needs to sit exactly on top of the video Element's actual footprint.
		const offsetX = (canvas.width - renderW) / 2;
		const offsetY = (canvas.height - renderH) / 2;

		let videoNaturalW = renderW;
		let videoNaturalH = renderH;
		if (videoEl instanceof HTMLVideoElement) {
			videoNaturalW = videoEl.videoWidth;
			videoNaturalH = videoEl.videoHeight;
		} else if (videoEl instanceof HTMLImageElement) {
			videoNaturalW = videoEl.naturalWidth;
			videoNaturalH = videoEl.naturalHeight;
		}

		// scaleX/Y maps the backend YOLO downscaled tracking resolution (e.g. 1280px) -> Screen
		const scaleX = renderW / videoRes.w;
		const scaleY = renderH / videoRes.h;

		// zoneScaleX/Y maps the original high-res camera size (which was used during Zone creation) -> Screen
		const zoneScaleX = videoNaturalW ? renderW / videoNaturalW : scaleX;
		const zoneScaleY = videoNaturalH ? renderH / videoNaturalH : scaleY;

		// Draw zones
		zones.forEach((zone) => {
			if (!zone.points || zone.points.length < 2) return;

			ctx.beginPath();
			ctx.strokeStyle = zone.color || '#00ff00';
			ctx.lineWidth = 2;
			ctx.setLineDash([5, 5]);

			const firstPt = zone.points[0];
			ctx.moveTo(offsetX + firstPt.x * zoneScaleX, offsetY + firstPt.y * zoneScaleY);

			for (let i = 1; i < zone.points.length; i++) {
				ctx.lineTo(
					offsetX + zone.points[i].x * zoneScaleX,
					offsetY + zone.points[i].y * zoneScaleY
				);
			}
			if (zone.type === 'polygon') ctx.closePath();
			ctx.stroke();
			ctx.setLineDash([]);

			// Semi-transparent fill
			ctx.fillStyle = (zone.color || '#00ff00') + '1a';
			ctx.fill();
		});

		// Draw boxes with zone-aware colors (matching video-analytics)
		boxes.forEach((box) => {
			// Orange = in zone, green = already counted, red = uncounted
			let color = '#ff0000';
			if (box.in_zone) color = '#ff8c00';
			else if (box.is_counted) color = '#00c800';

			ctx.strokeStyle = color;
			ctx.lineWidth = 2;

			const scaledX = offsetX + box.x * scaleX;
			const scaledY = offsetY + box.y * scaleY;
			const scaledW = box.w * scaleX;
			const scaledH = box.h * scaleY;

			ctx.strokeRect(scaledX, scaledY, scaledW, scaledH);

			if (box.label) {
				const labelText = `${box.label} #${box.id}`;
				ctx.font = 'bold 13px Inter, Arial, sans-serif';
				const textWidth = ctx.measureText(labelText).width + 10;
				ctx.fillStyle = color;
				ctx.fillRect(scaledX, scaledY - 22, textWidth, 22);
				ctx.fillStyle = '#ffffff';
				ctx.fillText(labelText, scaledX + 5, scaledY - 6);
			}
		});

		// Count overlay (top-left)
		if (trackCount > 0) {
			const countText = `Count: ${trackCount}`;
			ctx.font = 'bold 20px Inter, Arial, sans-serif';
			const tw = ctx.measureText(countText).width;
			ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
			ctx.fillRect(10, 10, tw + 20, 32);
			ctx.fillStyle = '#ffffff';
			ctx.fillText(countText, 20, 34);
		}
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
					<!-- TODO: MJPEG Proxy Route disconnected
						The backend MJPEG proxy was removed at `/api/cameras/stream`. 
						
						Previous code:
						src={`http://localhost:8000/api/cameras/stream/${taskId}`}
						-->
					<img
						src=""
						alt="Live Stream (Disconnected)"
						class="h-full w-full object-contain"
						crossorigin="anonymous"
					/>
					<canvas use:overlayAction class="pointer-events-none absolute top-0 left-0 h-full w-full"
					></canvas>
				</AspectRatio>
			</div>

			<div class="grid grid-cols-1 gap-4 md:grid-cols-4">
				<div class="grid grid-cols-2 gap-4 sm:grid-cols-4 md:col-span-3">
					<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
						<div class="text-sm font-semibold text-muted-foreground">Detection Model</div>
						<div class="mt-1 text-lg font-medium tracking-tight">{modelName} (Live)</div>
					</div>
					<div class="rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
						<div class="text-sm font-semibold text-muted-foreground">Total Unique Objects</div>
						<div class="mt-1 text-3xl font-bold tracking-tight text-primary">{trackCount}</div>
					</div>
					<!-- Render a metric card for each active zone -->
					{#each zones as zone}
						<div
							class="relative overflow-hidden rounded-lg border bg-card p-4 text-card-foreground shadow-sm"
						>
							<div
								class="absolute top-0 bottom-0 left-0 w-1"
								style="background-color: {zone.color || '#00ff00'}"
							></div>
							<div class="truncate pl-2 text-sm font-semibold text-muted-foreground">
								{zone.id.length > 8 ? `Zone ${zone.id.slice(0, 4)}` : zone.id}
							</div>
							<div class="mt-1 pl-2 text-3xl font-bold tracking-tight">
								{zoneCounts[zone.id] || 0}
							</div>
						</div>
					{/each}
				</div>

				<!-- Activity Sidebar -->
				<div
					class="flex h-64 flex-col overflow-hidden rounded-lg border bg-card shadow-sm md:col-span-1 md:h-auto"
				>
					<div class="border-b bg-muted/30 p-3">
						<h3 class="text-sm font-bold tracking-tight">Recent Activity</h3>
					</div>
					<div class="flex-1 overflow-y-auto p-0">
						{#if activityLogs.length === 0}
							<div
								class="flex h-full items-center justify-center p-4 text-center text-sm text-muted-foreground"
							>
								Waiting for events...
							</div>
						{:else}
							<ul class="divide-y divide-border/50">
								{#each activityLogs as log (log.id)}
									<li class="p-3 text-sm transition-colors hover:bg-muted/30">
										<div class="flex flex-col gap-1">
											<span class="text-xs font-medium text-muted-foreground">{log.time}</span>
											<span>{log.message}</span>
										</div>
									</li>
								{/each}
							</ul>
						{/if}
					</div>
				</div>
			</div>
		</div>
	</div>
</div>
