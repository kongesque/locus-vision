<script lang="ts">
	import { SvelteSet } from 'svelte/reactivity';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import {
		Download,
		Trash2,
		Loader2,
		Cpu,
		Zap,
		HardDrive,
		Check,
		AlertCircle,
		Upload,
		FileUp
	} from '@lucide/svelte';

	const API_URL = 'http://localhost:8000';

	interface ModelEntry {
		name: string;
		label: string;
		family: string;
		purpose: string;
		classes: string | string[];
		installed: boolean;
		active_format: string | null;
		size_mb: number | null;
		fps_estimate: number | null;
		available_formats: string[];
	}

	interface Props {
		backends: string[];
		models: ModelEntry[];
	}

	let { backends, models }: Props = $props();

	let downloadingModels = new SvelteSet<string>();
	let removingModels = new SvelteSet<string>();
	let downloadStatus = $state<Record<string, string>>({});

	let isDragging = $state(false);
	let uploadState = $state<'idle' | 'uploading' | 'success' | 'error'>('idle');
	let uploadProgress = $state('');
	let uploadError = $state('');
	let uploadWarnings = $state<string[]>([]);

	let installedModels = $derived(models.filter((m) => m.installed));
	let availableModels = $derived(models.filter((m) => !m.installed));

	// Readable hardware names
	function formatBackend(backend: string): string {
		const map: Record<string, string> = {
			hailo: 'Hailo-8L',
			onnx_cuda: 'CUDA GPU',
			onnx_coreml: 'CoreML',
			onnx_int8: 'CPU INT8',
			onnx_fp16: 'CPU FP16',
			onnx_fp32: 'CPU FP32'
		};
		return map[backend] ?? backend;
	}

	function formatPurpose(purpose: string): string {
		const map: Record<string, string> = {
			detection: 'Detection',
			pose: 'Pose',
			segmentation: 'Segmentation',
			'person-face': 'Person + Face'
		};
		return map[purpose] ?? purpose;
	}

	function formatSize(mb: number | null): string {
		if (mb === null) return '';
		if (mb < 1) return `${(mb * 1024).toFixed(0)} KB`;
		return `${mb.toFixed(1)} MB`;
	}

	// Hardware badge styling
	function getHardwareBadges(): { label: string; variant: 'default' | 'secondary' | 'outline' }[] {
		const result: { label: string; variant: 'default' | 'secondary' | 'outline' }[] = [];
		if (backends.includes('hailo')) result.push({ label: 'Hailo-8L', variant: 'default' });
		if (backends.includes('onnx_cuda')) result.push({ label: 'CUDA GPU', variant: 'default' });
		if (backends.includes('onnx_coreml')) result.push({ label: 'CoreML', variant: 'default' });
		// Always have CPU
		const cpuLabel = backends.includes('onnx_int8') ? 'CPU' : 'CPU FP32';
		result.push({ label: cpuLabel, variant: 'secondary' });
		return result;
	}

	async function handleDownload(modelName: string) {
		downloadingModels.add(modelName);
		downloadStatus[modelName] = 'starting';

		try {
			// Determine best precision for download based on backends
			let precision = 'fp32';
			if (backends.includes('onnx_int8')) precision = 'int8';
			else if (backends.includes('onnx_fp16')) precision = 'fp16';

			const res = await fetch(`${API_URL}/api/models/download`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ model_name: modelName, precision })
			});

			if (!res.ok) {
				downloadStatus[modelName] = 'error';
				downloadingModels.delete(modelName);
				return;
			}

			// Poll for completion
			pollDownload(modelName, `${modelName}_${precision}`);
		} catch {
			downloadStatus[modelName] = 'error';
			downloadingModels.delete(modelName);
		}
	}

	function pollDownload(modelName: string, jobId: string) {
		const interval = setInterval(async () => {
			try {
				const res = await fetch(`${API_URL}/api/models/download/status`);
				if (!res.ok) return;

				const statuses = await res.json();
				const job = statuses[jobId];

				if (!job) return;

				downloadStatus[modelName] = job.status;

				if (job.status === 'done') {
					clearInterval(interval);
					downloadingModels.delete(modelName);
					// Refresh model list from parent via re-fetch
					await refreshModels();
				} else if (job.status === 'error') {
					clearInterval(interval);
					downloadingModels.delete(modelName);
				}
			} catch {
				// Keep polling
			}
		}, 1500);
	}

	async function handleRemove(modelName: string) {
		removingModels.add(modelName);

		try {
			const res = await fetch(`${API_URL}/api/models/${modelName}`, {
				method: 'DELETE'
			});

			if (res.ok) {
				await refreshModels();
			}
		} catch {
			// Silently fail
		} finally {
			removingModels.delete(modelName);
		}
	}

	function handleDragOver(e: DragEvent) {
		e.preventDefault();
		isDragging = true;
	}

	function handleDragLeave(e: DragEvent) {
		e.preventDefault();
		isDragging = false;
	}

	async function handleDrop(e: DragEvent) {
		e.preventDefault();
		isDragging = false;

		const files = e.dataTransfer?.files;
		if (!files?.length) return;
		await uploadFile(files[0]);
	}

	function handleFileSelect(e: Event) {
		const input = e.target as HTMLInputElement;
		if (!input.files?.length) return;
		uploadFile(input.files[0]);
		input.value = '';
	}

	async function uploadFile(file: File) {

		const validExtensions = ['.onnx', '.tflite', '.pt'];
		if (!validExtensions.some((ext) => file.name.endsWith(ext))) {
			uploadState = 'error';
			uploadError = 'Supported formats: .onnx, .tflite, .pt';
			return;
		}

		uploadState = 'uploading';
		uploadProgress = file.name.endsWith('.pt')
			? `Uploading and converting ${file.name} to ONNX...`
			: `Uploading ${file.name}...`;
		uploadError = '';
		uploadWarnings = [];

		try {
			const formData = new FormData();
			formData.append('file', file);

			const res = await fetch(`${API_URL}/api/models/upload`, {
				method: 'POST',
				body: formData
			});

			if (!res.ok) {
				const data = await res.json().catch(() => null);
				throw new Error(data?.detail ?? `Upload failed (${res.status})`);
			}

			const result = await res.json();
			uploadState = 'success';
			uploadProgress = `${result.filename} uploaded (${result.size_mb} MB)`;
			uploadWarnings = result.warnings ?? [];
			await refreshModels();

			setTimeout(() => {
				uploadState = 'idle';
				uploadProgress = '';
				uploadWarnings = [];
			}, 5000);
		} catch (err) {
			uploadState = 'error';
			uploadError = err instanceof Error ? err.message : 'Upload failed';
		}
	}

	async function refreshModels() {
		try {
			const res = await fetch(`${API_URL}/api/models/registry`);
			if (res.ok) {
				const data = await res.json();
				models = data.models ?? [];
			}
		} catch {
			// Keep existing data
		}
	}

	let hardwareBadges = $derived(getHardwareBadges());
</script>

<!-- Hardware Detection -->
<Card.Root>
	<Card.Header>
		<Card.Title class="text-lg">Hardware</Card.Title>
		<Card.Description>Detected inference backends for this device</Card.Description>
	</Card.Header>
	<Card.Content>
		<div class="flex flex-wrap items-center gap-2">
			{#each hardwareBadges as hw (hw.label)}
				<Badge variant={hw.variant} class="gap-1.5 px-3 py-1">
					{#if hw.label === 'Hailo-8L'}
						<Zap class="size-3" />
					{:else if hw.label === 'CUDA GPU'}
						<HardDrive class="size-3" />
					{:else}
						<Cpu class="size-3" />
					{/if}
					{hw.label}
				</Badge>
			{/each}
		</div>

		{#if backends.length === 0}
			<div class="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
				<AlertCircle class="size-4" />
				<span>No backends detected. Restart the backend to re-detect hardware.</span>
			</div>
		{/if}
	</Card.Content>
</Card.Root>

<!-- Upload Model -->
<Card.Root>
	<Card.Header>
		<Card.Title class="text-lg">Upload Model</Card.Title>
		<Card.Description>Drag and drop an ONNX model file or click to browse</Card.Description>
	</Card.Header>
	<Card.Content>
		<input
			type="file"
			accept=".onnx,.tflite,.pt"
			class="hidden"
			id="model-upload-input"
			onchange={handleFileSelect}
		/>
		<label
			for="model-upload-input"
			class="flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed p-8 text-center transition-colors {isDragging
				? 'border-primary bg-primary/5'
				: 'border-muted-foreground/25 hover:border-muted-foreground/50'}"
			ondragover={handleDragOver}
			ondragleave={handleDragLeave}
			ondrop={handleDrop}
		>
			{#if uploadState === 'uploading'}
				<Loader2 class="size-8 animate-spin text-muted-foreground" />
				<p class="text-sm text-muted-foreground">{uploadProgress}</p>
			{:else if uploadState === 'success'}
				<Check class="size-8 text-green-500" />
				<p class="text-sm text-green-600">{uploadProgress}</p>
				{#each uploadWarnings as warning (warning)}
					<p class="text-xs text-yellow-600">{warning}</p>
				{/each}
			{:else if uploadState === 'error'}
				<AlertCircle class="size-8 text-destructive" />
				<p class="text-sm text-destructive">{uploadError}</p>
				<p class="text-xs text-muted-foreground">Click or drop to try again</p>
			{:else}
				{#if isDragging}
					<FileUp class="size-8 text-primary" />
					<p class="text-sm font-medium text-primary">Drop model here</p>
				{:else}
					<Upload class="size-8 text-muted-foreground" />
					<div>
						<p class="text-sm font-medium">Drop model file here</p>
						<p class="mt-1 text-xs text-muted-foreground">
							YOLO models — ONNX, TFLite, or PyTorch (.pt auto-converts to ONNX)
						</p>
					</div>
				{/if}
			{/if}
		</label>
	</Card.Content>
</Card.Root>

<!-- Installed Models -->
<Card.Root>
	<Card.Header>
		<Card.Title class="text-lg">Installed</Card.Title>
		<Card.Description>
			{installedModels.length} model{installedModels.length !== 1 ? 's' : ''} ready to use
		</Card.Description>
	</Card.Header>
	<Card.Content>
		{#if installedModels.length === 0}
			<div class="rounded-lg border border-dashed p-6 text-center">
				<p class="text-sm text-muted-foreground">
					No models installed yet. Download one below to get started.
				</p>
			</div>
		{:else}
			<div class="space-y-3">
				{#each installedModels as model (model.name)}
					<div
						class="flex items-center justify-between rounded-lg border bg-card p-4 transition-colors hover:bg-muted/50"
					>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<p class="font-medium">{model.label}</p>
								<Badge variant="outline" class="text-xs">
									{formatPurpose(model.purpose)}
								</Badge>
							</div>
							<div
								class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
							>
								{#if model.active_format}
									<span class="flex items-center gap-1">
										<Check class="size-3 text-green-500" />
										{formatBackend(model.active_format)}
									</span>
								{/if}
								{#if model.fps_estimate}
									<span>~{model.fps_estimate} fps</span>
								{/if}
								{#if model.size_mb}
									<span>{formatSize(model.size_mb)}</span>
								{/if}
							</div>
						</div>
						<Button
							variant="ghost"
							size="sm"
							class="text-destructive hover:text-destructive cursor-pointer"
							disabled={removingModels.has(model.name)}
							onclick={() => handleRemove(model.name)}
						>
							{#if removingModels.has(model.name)}
								<Loader2 class="size-4 animate-spin" />
							{:else}
								<Trash2 class="size-4" />
							{/if}
						</Button>
					</div>
				{/each}
			</div>
		{/if}
	</Card.Content>
</Card.Root>

<!-- Available Models -->
{#if availableModels.length > 0}
	<Card.Root>
		<Card.Header>
			<Card.Title class="text-lg">Available</Card.Title>
			<Card.Description>
				Models compatible with your hardware — download to use
			</Card.Description>
		</Card.Header>
		<Card.Content>
			<div class="space-y-3">
				{#each availableModels as model (model.name)}
					<div
						class="flex items-center justify-between rounded-lg border bg-card p-4 transition-colors hover:bg-muted/50"
					>
						<div class="min-w-0 flex-1">
							<div class="flex items-center gap-2">
								<p class="font-medium">{model.label}</p>
								<Badge variant="outline" class="text-xs">
									{formatPurpose(model.purpose)}
								</Badge>
							</div>
							<div
								class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground"
							>
								{#if model.available_formats.length > 0}
									<span>{formatBackend(model.available_formats[0])}</span>
								{/if}
								{#if model.fps_estimate}
									<span>~{model.fps_estimate} fps</span>
								{/if}
								{#if model.size_mb}
									<span>{formatSize(model.size_mb)}</span>
								{/if}
							</div>
						</div>

						<div class="flex items-center gap-2">
							{#if downloadingModels.has(model.name)}
								<div class="flex items-center gap-2 text-sm text-muted-foreground">
									<Loader2 class="size-4 animate-spin" />
									<span class="capitalize"
										>{downloadStatus[model.name] ?? 'starting'}</span
									>
								</div>
							{:else if downloadStatus[model.name] === 'error'}
								<span class="text-xs text-destructive">Failed</span>
								<Button
									variant="outline"
									size="sm"
									class="cursor-pointer"
									onclick={() => handleDownload(model.name)}
								>
									Retry
								</Button>
							{:else}
								<Button
									variant="outline"
									size="sm"
									class="cursor-pointer"
									onclick={() => handleDownload(model.name)}
								>
									<Download class="mr-1.5 size-3.5" />
									Download
								</Button>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</Card.Content>
	</Card.Root>
{/if}
