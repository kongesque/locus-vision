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
		AlertCircle
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
							class="text-destructive hover:text-destructive"
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
									onclick={() => handleDownload(model.name)}
								>
									Retry
								</Button>
							{:else}
								<Button
									variant="outline"
									size="sm"
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
