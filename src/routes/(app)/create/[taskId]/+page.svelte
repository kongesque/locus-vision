<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { setVideoContext } from '$lib/stores/video-store.svelte';
	import * as Card from '$lib/components/ui/card';
	import VideoPreview from '$lib/components/create/video-preview.svelte';
	import ToolsPanel, { type YoloModel } from '$lib/components/create/tools-panel.svelte';
	import type { Point, Zone } from '$lib/components/create/drawing-canvas.svelte';

	// Get taskId from URL params
	const taskId = $derived($page.params.taskId);

	// Initialize Video Store (Context)
	// We might want to load the video URL based on taskId here in a real app
	// For now, we'll initialize the store.
	setVideoContext({
		// In a real app, you might fetch the video URL for this taskId
		// For demo, we might start empty or user sets it.
		// If the previous page passed state, we could use it.
		// Assuming the user will upload or select a video,
		// OR if this page implies the video IS the task's video.
		// The original code used `useVideo()` from context but didn't show where it was provided.
		// I'll assume we need to provide it here.
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

	function handleProcess() {
		// TODO: FastAPI Backend Integration
		/*
        fetch(`http://localhost:8000/api/video/${taskId}/process`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ zones, model: selectedModel }),
        });
        */

		// Redirect immediately to dashboard
		goto('/video-analytics');
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
