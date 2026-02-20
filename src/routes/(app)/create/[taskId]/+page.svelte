<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { setVideoContext } from '$lib/stores/video-store.svelte';
	import * as Card from '$lib/components/ui/card';
	import VideoPreview from '$lib/components/create/video-preview.svelte';
	import ToolsPanel, { type YoloModel } from '$lib/components/create/tools-panel.svelte';
	import type { Point, Zone } from '$lib/components/create/drawing-canvas.svelte';

	import { videoStore } from '$lib/stores/video.svelte';

	// Get taskId from URL params
	const taskId = $derived($page.params.taskId);

	// Initialize Video Store (Context)
	// We load the video details from the global store if available
	setVideoContext({
		videoUrl: videoStore.videoUrl || null,
		videoType: videoStore.videoType as 'file' | 'stream' | 'rtsp' | null,
		videoStream: videoStore.videoStream || null,
		videoConfig: videoStore.videoType === 'rtsp' ? { url: videoStore.videoUrl } : null
	});

	// State
	let zones = $state<Zone[]>([]);
	let selectedZoneId = $state<string | null>(null);
	let drawingMode = $state<'polygon' | 'line'>('polygon');
	let fullFrameClasses = $state<string[]>([]);
	let selectedModel = $state<YoloModel>('yolo11n');

	function handleZoneCreated(points: Point[]) {
		const newZone: Zone = {
			id: crypto.randomUUID(),
			points: points,
			type: drawingMode,
			name: `${drawingMode === 'line' ? 'Line' : 'Zone'} ${zones.length + 1}`,
			classes: [], // Empty means detect all classes
			color: '#fbbd05'
		};
		zones = [...zones, newZone];
		selectedZoneId = newZone.id; // Auto-select new zone
	}

	function handleZoneRenamed(id: string, name: string) {
		zones = zones.map((z) => (z.id === id ? { ...z, name: name } : z));
	}

	function handleZoneClassesChanged(id: string, classes: string[]) {
		zones = zones.map((z) => (z.id === id ? { ...z, classes: classes } : z));
	}

	function handleZoneSelected(id: string | null) {
		selectedZoneId = id;
	}

	function handleZoneUpdated(id: string, newPoints: Point[]) {
		zones = zones.map((z) => (z.id === id ? { ...z, points: newPoints } : z));
	}

	function handleDeleteZone(id: string, e: MouseEvent) {
		e.stopPropagation();
		zones = zones.filter((z) => z.id !== id);
		if (selectedZoneId === id) {
			selectedZoneId = null;
		}
	}

	async function handleProcess() {
		if (!videoStore.videoUrl && videoStore.videoType !== 'stream') {
			alert('No video or stream source available');
			return;
		}

		if (videoStore.videoType === 'file' && videoStore.videoUrl) {
			// --- Existing File Upload Flow ---
			// Convert blob URL to File (fast, in-memory — no network)
			const response = await fetch(videoStore.videoUrl);
			const blob = await response.blob();
			const file = new File([blob], 'video.mp4', { type: 'video/mp4' });

			const formData = new FormData();
			formData.append('video', file);
			formData.append('zones', JSON.stringify(zones));
			formData.append('model', selectedModel);
			formData.append('classes', JSON.stringify(fullFrameClasses));

			// Fire-and-forget: upload in background
			fetch(`http://localhost:8000/api/video/${taskId}/process`, {
				method: 'POST',
				body: formData
			}).catch((err) => console.error('Upload failed:', err));

			// Redirect immediately to task result page
			goto(`/video-analytics/${taskId}`);
		} else {
			// --- New Camera Analytics Flow ---
			try {
				const response = await fetch(`http://localhost:8000/api/cameras/${taskId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						zones: zones,
						model_name: selectedModel,
						classes: fullFrameClasses
					})
				});

				if (!response.ok) {
					console.error('Failed to update camera config');
					alert('Failed to configure camera analytics');
					return;
				}

				// Redirect to livestream view with WebSocket bounds overlay
				goto(`/livestream/${taskId}`);
			} catch (err) {
				console.error(err);
				alert('Camera configuration error: ' + String(err));
			}
		}
	}
</script>

<div class="flex h-[calc(100vh-4rem)] flex-1 flex-col gap-4 p-4">
	<!-- Main Content -->
	<div class="flex min-h-0 flex-1 gap-4">
		<!-- Left: Video Canvas -->
		<Card.Root class="flex flex-[3] flex-col overflow-hidden p-0">
			<VideoPreview
				{zones}
				{selectedZoneId}
				{drawingMode}
				onZoneCreated={handleZoneCreated}
				onZoneSelected={handleZoneSelected}
				onZoneUpdated={handleZoneUpdated}
			/>
		</Card.Root>

		<!-- Right: Tools -->
		<div class="flex min-w-[350px] flex-1 flex-col">
			<ToolsPanel
				{zones}
				{selectedZoneId}
				{drawingMode}
				{fullFrameClasses}
				{selectedModel}
				onDrawingModeChange={(mode) => (drawingMode = mode)}
				onZoneSelected={handleZoneSelected}
				onDeleteZone={handleDeleteZone}
				onProcess={handleProcess}
				onZoneRenamed={handleZoneRenamed}
				onZoneClassesChanged={handleZoneClassesChanged}
				onFullFrameClassesChanged={(classes) => (fullFrameClasses = classes)}
				onModelChange={(model) => (selectedModel = model)}
			/>
		</div>
	</div>
</div>
