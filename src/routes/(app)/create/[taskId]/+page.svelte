<script lang="ts">
	import { page } from '$app/stores';
	import { API_URL } from '$lib/api';
	import { goto } from '$app/navigation';
	import { setVideoContext } from '$lib/stores/video-store.svelte';
	import * as Card from '$lib/components/ui/card';
	import VideoPreview from '$lib/components/create/video-preview.svelte';
	import ToolsPanel from '$lib/components/create/tools-panel.svelte';
	import type { Point, Zone } from '$lib/components/create/drawing-canvas.svelte';
	import { pickZoneColor } from '$lib/zone-colors';
	import { onMount, onDestroy } from 'svelte';

	import { videoStore } from '$lib/stores/video.svelte';

	// Get taskId from URL params
	const taskId = $derived($page.params.taskId);

	// Initialize Video Store (Context)
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
	let confidenceThreshold = $state<number>(0.25);

	// Drawing state lifted from canvas (for keyboard coordination)
	let currentPoints = $state<Point[]>([]);
	let isDrawing = $state(false);

	// Undo history for committed zones
	const HISTORY_LIMIT = 50;
	let history = $state<Zone[][]>([]);

	function pushHistory() {
		const snapshot = zones.map((z) => ({ ...z, points: z.points.map((p) => ({ ...p })) }));
		history = [...history, snapshot];
		if (history.length > HISTORY_LIMIT) history = history.slice(-HISTORY_LIMIT);
	}

	function undo() {
		if (history.length === 0) return;
		const prev = history[history.length - 1];
		history = history.slice(0, -1);
		zones = prev;
		if (selectedZoneId && !prev.some((z) => z.id === selectedZoneId)) {
			selectedZoneId = null;
		}
	}

	// Installed models from registry API
	let installedModels = $state<
		{ name: string; label: string; fps_estimate?: number | null; active_format?: string | null }[]
	>([]);

	// FPS: default depends on flow type (12 = video analytics, 24 = livestream)
	const defaultFps = $derived(videoStore.videoType === 'file' ? 12 : 24);
	let fps = $state<number>(videoStore.videoType === 'file' ? 12 : 24);

	onMount(() => {
		fetchInstalledModels();
	});

	async function fetchInstalledModels() {
		try {
			const res = await fetch(`${API_URL}/api/models/registry`);
			if (res.ok) {
				const data = await res.json();
				installedModels = (data.models ?? []).filter((m: any) => m.installed);
				// Use system default model, fall back to yolo11n, then first installed
				const systemDefault = data.default_model || 'yolo11n';
				selectedModel =
					installedModels.find((m) => m.name === systemDefault)?.name ||
					installedModels.find((m) => m.name === 'yolo11n')?.name ||
					installedModels[0]?.name ||
					'';
			}
		} catch (err) {
			console.error('Failed to fetch models:', err);
		}
	}

	function handleZoneCreated(points: Point[]) {
		pushHistory();
		const newZone: Zone = {
			id: crypto.randomUUID(),
			points: points,
			type: drawingMode,
			name: `${drawingMode === 'line' ? 'Line' : 'Zone'} ${zones.length + 1}`,
			classes: [],
			color: pickZoneColor(zones.map((z) => z.color).filter((c): c is string => !!c)),
			direction: 'both'
		};
		zones = [...zones, newZone];
		selectedZoneId = newZone.id;
	}

	function handleZoneRenamed(id: string, name: string) {
		pushHistory();
		zones = zones.map((z) => (z.id === id ? { ...z, name: name } : z));
	}

	function handleZoneClassesChanged(id: string, classes: string[]) {
		pushHistory();
		zones = zones.map((z) => (z.id === id ? { ...z, classes: classes } : z));
	}

	function handleZoneDirectionChanged(id: string, direction: 'both' | 'in' | 'out') {
		pushHistory();
		zones = zones.map((z) => (z.id === id ? { ...z, direction } : z));
	}

	function handleZoneSelected(id: string | null) {
		selectedZoneId = id;
	}

	// History snapshot is taken in the canvas via onBeforeEdit at drag/insert start,
	// so per-frame point updates don't push history.
	function handleZoneUpdated(id: string, newPoints: Point[]) {
		zones = zones.map((z) => (z.id === id ? { ...z, points: newPoints } : z));
	}

	function deleteZoneById(id: string) {
		pushHistory();
		zones = zones.filter((z) => z.id !== id);
		if (selectedZoneId === id) {
			selectedZoneId = null;
		}
	}

	function handleDeleteZone(id: string, e: MouseEvent) {
		e.stopPropagation();
		deleteZoneById(id);
	}

	function handleKeydown(e: KeyboardEvent) {
		const target = e.target as HTMLElement | null;
		if (
			target &&
			(target.tagName === 'INPUT' ||
				target.tagName === 'TEXTAREA' ||
				target.tagName === 'SELECT' ||
				target.isContentEditable)
		) {
			return;
		}

		// Cmd/Ctrl+Z → undo
		if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
			e.preventDefault();
			undo();
			return;
		}

		// Esc → cancel in-progress drawing
		if (e.key === 'Escape') {
			if (currentPoints.length > 0 || isDrawing) {
				e.preventDefault();
				currentPoints = [];
				isDrawing = false;
			}
			return;
		}

		// Backspace / Delete
		if (e.key === 'Backspace' || e.key === 'Delete') {
			if (currentPoints.length > 0) {
				e.preventDefault();
				currentPoints = currentPoints.slice(0, -1);
				if (currentPoints.length === 0) isDrawing = false;
			} else if (selectedZoneId) {
				e.preventDefault();
				deleteZoneById(selectedZoneId);
			}
		}
	}

	onMount(() => {
		window.addEventListener('keydown', handleKeydown);
	});

	onDestroy(() => {
		if (typeof window !== 'undefined') {
			window.removeEventListener('keydown', handleKeydown);
		}
	});

	async function handleProcess(mode: 'zone-based' | 'full-frame') {
		if (!videoStore.videoUrl && videoStore.videoType !== 'stream') {
			alert('No video or stream source available');
			return;
		}

		const finalZones = mode === 'full-frame' ? [] : zones;
		const finalGlobalClasses = mode === 'zone-based' ? [] : fullFrameClasses;

		if (videoStore.videoType === 'file' && videoStore.videoUrl) {
			// --- File Upload Flow ---
			const response = await fetch(videoStore.videoUrl);
			const blob = await response.blob();
			const file = new File([blob], 'video.mp4', { type: 'video/mp4' });

			const formData = new FormData();
			formData.append('video', file);
			const normalizedZones = finalZones.map((z) => ({
				...z,
				points: z.points.map((p) => ({
					x: videoNaturalWidth ? p.x / videoNaturalWidth : 0,
					y: videoNaturalHeight ? p.y / videoNaturalHeight : 0
				}))
			}));

			formData.append('zones', JSON.stringify(normalizedZones));
			formData.append('classes', JSON.stringify(finalGlobalClasses));
			formData.append('model_name', selectedModel);
			formData.append('fps', String(fps));
			formData.append('confidence_threshold', String(confidenceThreshold));

			fetch(`${API_URL}/api/video/${taskId}/process`, {
				method: 'POST',
				body: formData
			}).catch((err) => console.error('Upload failed:', err));

			goto(`/video-analytics/${taskId}`, { replaceState: true });
		} else {
			// --- Camera Analytics Flow ---
			try {
				const normalizedZones = finalZones.map((z) => ({
					...z,
					points: z.points.map((p) => ({
						x: videoNaturalWidth ? p.x / videoNaturalWidth : 0,
						y: videoNaturalHeight ? p.y / videoNaturalHeight : 0
					}))
				}));

				const consolidatedClasses = Array.from(
					new Set([...finalGlobalClasses, ...finalZones.flatMap((z) => z.classes || [])])
				);

				const response = await fetch(`${API_URL}/api/cameras/${taskId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						zones: JSON.stringify(normalizedZones),
						classes: JSON.stringify(consolidatedClasses),
						model_name: selectedModel,
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

<div class="flex h-[calc(100vh-4rem)] flex-1 flex-col gap-4 overflow-hidden p-4">
	<!-- Main Content -->
	<div class="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row">
		<!-- Left: Video Canvas -->
		<Card.Root class="flex min-h-[250px] flex-col overflow-hidden p-0 lg:flex-[3]">
			<VideoPreview
				cameraId={taskId}
				{zones}
				{selectedZoneId}
				{drawingMode}
				onZoneCreated={handleZoneCreated}
				onZoneSelected={handleZoneSelected}
				onZoneUpdated={handleZoneUpdated}
				onBeforeEdit={pushHistory}
				bind:naturalWidth={videoNaturalWidth}
				bind:naturalHeight={videoNaturalHeight}
				bind:currentPoints
				bind:isDrawing
			/>
		</Card.Root>

		<!-- Right: Tools -->
		<div class="flex min-h-0 flex-1 flex-col overflow-hidden lg:max-w-[400px]">
			<ToolsPanel
				{zones}
				{selectedZoneId}
				{drawingMode}
				{fullFrameClasses}
				{selectedModel}
				{installedModels}
				{fps}
				onDrawingModeChange={(mode) => (drawingMode = mode)}
				onZoneSelected={handleZoneSelected}
				onDeleteZone={handleDeleteZone}
				onProcess={handleProcess}
				onZoneRenamed={handleZoneRenamed}
				onZoneClassesChanged={handleZoneClassesChanged}
				onZoneDirectionChanged={handleZoneDirectionChanged}
				onFullFrameClassesChanged={(classes) => (fullFrameClasses = classes)}
				onModelChange={(model) => (selectedModel = model)}
				onFpsChange={(v) => (fps = v)}
				{confidenceThreshold}
				onConfidenceThresholdChange={(v) => (confidenceThreshold = v)}
			/>
		</div>
	</div>
</div>
