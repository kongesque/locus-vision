<script lang="ts">
	import { page } from '$app/stores';
	import { API_URL } from '$lib/api';
	import { goto } from '$app/navigation';
	import { setVideoContext } from '$lib/stores/video-store.svelte';
	import * as Card from '$lib/components/ui/card';
	import VideoPreview from '$lib/components/create/video-preview.svelte';
	import ToolsPanel from '$lib/components/create/tools-panel.svelte';
	import type { Point, Zone } from '$lib/components/create/drawing-canvas.svelte';
	import { onMount } from 'svelte';

	import { videoStore } from '$lib/stores/video.svelte';

	// All YOLO11 model sizes with metadata
	export const YOLO11_MODELS = [
		{ value: 'yolo11n', label: 'YOLOv11 Nano', desc: 'Fastest', size: '~6MB' },
		{ value: 'yolo11s', label: 'YOLOv11 Small', desc: 'Fast', size: '~20MB' },
		{ value: 'yolo11m', label: 'YOLOv11 Medium', desc: 'Balanced', size: '~40MB' },
		{ value: 'yolo11l', label: 'YOLOv11 Large', desc: 'Accurate', size: '~50MB' },
		{ value: 'yolo11x', label: 'YOLOv11 Extra Large', desc: 'Most Accurate', size: '~115MB' }
	];

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
	let isProcessing = $state(false);
	let videoNaturalWidth = $state(1920);
	let videoNaturalHeight = $state(1080);
	let errorMsg = $state<string | null>(null);

	let zones = $state<Zone[]>([]);
	let selectedZoneId = $state<string | null>(null);
	let drawingMode = $state<'polygon' | 'line'>('polygon');
	let fullFrameClasses = $state<string[]>([]);
	let selectedModel = $state<string>('yolo11n');
	let selectedPrecision = $state<'fp32' | 'fp16' | 'int8'>('int8');
	let downloadedModels = $state<string[]>([]);
	let confidenceThreshold = $state<number>(0.25);

	// FPS: default depends on flow type (12 = video analytics, 24 = livestream)
	const defaultFps = $derived(videoStore.videoType === 'file' ? 12 : 24);
	let fps = $state<number>(videoStore.videoType === 'file' ? 12 : 24);

	// Model Download State
	let modelDownloadStatus = $state<{ status: string; error?: string } | null>(null);
	let isDownloadingModel = $derived(
		modelDownloadStatus?.status === 'starting' ||
			modelDownloadStatus?.status === 'downloading' ||
			modelDownloadStatus?.status === 'exporting'
	);

	// Combine model size + precision into the final model name for the backend
	const resolvedModelName = $derived.by(() => {
		if (selectedPrecision === 'int8') return `${selectedModel}_int8`;
		if (selectedPrecision === 'fp16') return `${selectedModel}_half`;
		return selectedModel; // fp32 = no suffix
	});

	const isModelMissing = $derived(!downloadedModels.includes(resolvedModelName));

	onMount(async () => {
		await fetchDownloadedModels();
	});

	async function fetchDownloadedModels() {
		try {
			const res = await fetch(`${API_URL}/api/models/registry`);
			if (res.ok) {
				downloadedModels = await res.json();
			}
		} catch (err) {
			console.error('Failed to fetch models:', err);
		}
	}

	async function handleDownloadModel() {
		try {
			const res = await fetch(`${API_URL}/api/models/download`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					model_name: selectedModel,
					precision: selectedPrecision
				})
			});
			if (!res.ok) throw new Error('Failed to start download');

			modelDownloadStatus = await res.json();
			pollDownloadStatus();
		} catch (err) {
			console.error(err);
			modelDownloadStatus = { status: 'error', error: String(err) };
		}
	}

	async function pollDownloadStatus() {
		if (!isDownloadingModel) return;

		try {
			const res = await fetch(`${API_URL}/api/models/download/status`);
			if (res.ok) {
				const statuses = await res.json();
				// The backend key is baseModel_precision e.g. "yolo11s_int8"
				const jobKey = `${selectedModel}_${selectedPrecision}`;
				if (statuses[jobKey]) {
					modelDownloadStatus = statuses[jobKey];

					if (modelDownloadStatus?.status === 'done') {
						await fetchDownloadedModels(); // Refresh available models
					}
				}
			}
		} catch (err) {
			console.error('Failed to poll status:', err);
		}

		// Continue polling if still active
		if (isDownloadingModel) {
			setTimeout(pollDownloadStatus, 1000);
		}
	}

	function handleZoneCreated(points: Point[]) {
		const newZone: Zone = {
			id: crypto.randomUUID(),
			points: points,
			type: drawingMode,
			name: `${drawingMode === 'line' ? 'Line' : 'Zone'} ${zones.length + 1}`,
			classes: [], // Empty means detect all classes
			color: '#fbbd05',
			direction: 'both'
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

	function handleZoneDirectionChanged(id: string, direction: 'both' | 'in' | 'out') {
		zones = zones.map((z) => (z.id === id ? { ...z, direction } : z));
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

	async function handleProcess(mode: 'zone-based' | 'full-frame') {
		if (!videoStore.videoUrl && videoStore.videoType !== 'stream') {
			alert('No video or stream source available');
			return;
		}

		// Depending on the mode, determine what to send to the backend
		const finalZones = mode === 'full-frame' ? [] : zones;
		const finalGlobalClasses = mode === 'zone-based' ? [] : fullFrameClasses;

		if (videoStore.videoType === 'file' && videoStore.videoUrl) {
			// --- Existing File Upload Flow ---
			// Convert blob URL to File (fast, in-memory — no network)
			const response = await fetch(videoStore.videoUrl);
			const blob = await response.blob();
			const file = new File([blob], 'video.mp4', { type: 'video/mp4' });

			const formData = new FormData();
			formData.append('video', file);
			// Normalize zones to relative coordinates [0.0 - 1.0]
			const normalizedZones = finalZones.map((z) => ({
				...z,
				points: z.points.map((p) => ({
					x: videoNaturalWidth ? p.x / videoNaturalWidth : 0,
					y: videoNaturalHeight ? p.y / videoNaturalHeight : 0
				}))
			}));

			formData.append('zones', JSON.stringify(normalizedZones));
			formData.append('classes', JSON.stringify(finalGlobalClasses));
			formData.append('model_name', resolvedModelName);
			formData.append('fps', String(fps));
			formData.append('confidence_threshold', String(confidenceThreshold));

			// Fire-and-forget: upload in background
			fetch(`${API_URL}/api/video/${taskId}/process`, {
				method: 'POST',
				body: formData
			}).catch((err) => console.error('Upload failed:', err));

			// Redirect immediately to task result page
			goto(`/video-analytics/${taskId}`, { replaceState: true });
		} else {
			// --- Camera Analytics Flow ---
			try {
				// Normalize zones to relative coordinates [0.0 - 1.0] before sending to backend
				const normalizedZones = finalZones.map((z) => ({
					...z,
					points: z.points.map((p) => ({
						x: videoNaturalWidth ? p.x / videoNaturalWidth : 0,
						y: videoNaturalHeight ? p.y / videoNaturalHeight : 0
					}))
				}));

				// Consolidate classes to ensure Activity Feed shows all selected classes
				const consolidatedClasses = Array.from(
					new Set([...finalGlobalClasses, ...finalZones.flatMap((z) => z.classes || [])])
				);

				const response = await fetch(`${API_URL}/api/cameras/${taskId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						zones: JSON.stringify(normalizedZones),
						classes: JSON.stringify(consolidatedClasses),
						model_name: resolvedModelName,
						fps: fps,
						confidence_threshold: confidenceThreshold,
						status: 'active'
					})
				});

				if (!response.ok) {
					const errData = await response.json().catch(() => ({ detail: 'Unknown error' }));
					throw new Error(errData.detail || 'Failed to save camera configuration');
				}

				goto(`/livestream/${taskId}`, { replaceState: true });
			} catch (err) {
				console.error(err);
				alert('Camera configuration error: ' + String(err));
			}
		}
	}
</script>

<svelte:head>
	<title>Create · Locus</title>
</svelte:head>

<div class="flex h-[calc(100vh-4rem)] flex-1 flex-col gap-4 p-4">
	<!-- Main Content -->
	<div class="flex min-h-0 flex-1 gap-4">
		<!-- Left: Video Canvas -->
		<Card.Root class="flex flex-[3] flex-col overflow-hidden p-0">
			<VideoPreview
				cameraId={taskId}
				{zones}
				{selectedZoneId}
				{drawingMode}
				onZoneCreated={handleZoneCreated}
				onZoneSelected={handleZoneSelected}
				onZoneUpdated={handleZoneUpdated}
				bind:naturalWidth={videoNaturalWidth}
				bind:naturalHeight={videoNaturalHeight}
			/>
		</Card.Root>

		<!-- Right: Tools -->
		<div class="flex min-w-[350px] flex-1 flex-col min-h-0 overflow-hidden">
			<ToolsPanel
				{zones}
				{selectedZoneId}
				{drawingMode}
				{fullFrameClasses}
				{selectedModel}
				{selectedPrecision}
				allModels={YOLO11_MODELS}
				{downloadedModels}
				{isModelMissing}
				{isDownloadingModel}
				{modelDownloadStatus}
				{fps}
				onDrawingModeChange={(mode) => (drawingMode = mode)}
				onZoneSelected={handleZoneSelected}
				onDeleteZone={handleDeleteZone}
				onProcess={handleProcess}
				onDownloadModel={handleDownloadModel}
				onZoneRenamed={handleZoneRenamed}
				onZoneClassesChanged={handleZoneClassesChanged}
				onZoneDirectionChanged={handleZoneDirectionChanged}
				onFullFrameClassesChanged={(classes) => (fullFrameClasses = classes)}
				onModelChange={(model) => (selectedModel = model)}
				onPrecisionChange={(p: 'fp32' | 'fp16' | 'int8') => {
					selectedPrecision = p;
					modelDownloadStatus = null; // reset status on change
				}}
				onFpsChange={(v) => (fps = v)}
				{confidenceThreshold}
				onConfidenceThresholdChange={(v) => (confidenceThreshold = v)}
			/>
		</div>
	</div>
</div>
