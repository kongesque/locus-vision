<script lang="ts">
	import { goto } from '$app/navigation';
	import { Upload, ArrowUp, X } from '@lucide/svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { videoStore } from '$lib/stores/video.svelte.js';
	import { cn } from '$lib/utils.js';

	let files = $state<File[]>([]);
	let isDragging = $state(false);
	let fileInputRef: HTMLInputElement;

	const handleDragOver = (e: DragEvent) => {
		e.preventDefault();
		isDragging = true;
	};

	const handleDragLeave = (e: DragEvent) => {
		e.preventDefault();
		isDragging = false;
	};

	const handleDrop = (e: DragEvent) => {
		e.preventDefault();
		isDragging = false;
		const droppedFiles = e.dataTransfer?.files;
		if (droppedFiles) {
			addFiles(droppedFiles);
		}
	};

	const handleFileSelect = (e: Event) => {
		const target = e.target as HTMLInputElement;
		const selectedFiles = target.files;
		if (selectedFiles) {
			addFiles(selectedFiles);
		}
	};

	function addFiles(fileList: FileList) {
		const videoFiles = Array.from(fileList).filter((f) => f.type.startsWith('video/'));
		// Deduplicate by name+size
		for (const f of videoFiles) {
			if (!files.some((existing) => existing.name === f.name && existing.size === f.size)) {
				files = [...files, f];
			}
		}
	}

	const handleUploadClick = () => {
		fileInputRef?.click();
	};

	const handleRemoveFile = (index: number) => {
		files = files.filter((_, i) => i !== index);
		if (fileInputRef) {
			fileInputRef.value = '';
		}
	};

	const handleClearAll = () => {
		files = [];
		if (fileInputRef) {
			fileInputRef.value = '';
		}
	};

	const handleSubmit = async () => {
		if (files.length === 0) return;

		// For a single file, use the existing create flow
		const firstFile = files[0];
		const taskId = crypto.randomUUID();
		const objectUrl = URL.createObjectURL(firstFile);

		videoStore.setVideoUrl(objectUrl);
		videoStore.setVideoType('file');

		// Store extra files in sessionStorage so the create page can batch-enqueue them
		if (files.length > 1) {
			const batchInfo = files.map((f, i) => ({
				name: f.name,
				size: f.size,
				taskId: i === 0 ? taskId : crypto.randomUUID()
			}));
			sessionStorage.setItem('batch_files', JSON.stringify(batchInfo));

			// Store actual file objects in a module-level map for the create page to access
			const batchMap: Record<string, File> = {};
			for (let i = 0; i < files.length; i++) {
				const id = batchInfo[i].taskId;
				batchMap[id] = files[i];
			}
			(window as any).__batchFiles = batchMap;
		} else {
			sessionStorage.removeItem('batch_files');
			(window as any).__batchFiles = { [taskId]: firstFile };
		}

		goto(`/create/${taskId}`);
	};

	function formatSize(bytes: number): string {
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
</script>

<Card.Root class="w-full gap-0 p-0">
	<!-- Hidden File Input (multiple) -->
	<input
		bind:this={fileInputRef}
		type="file"
		accept="video/*"
		multiple
		onchange={handleFileSelect}
		class="hidden"
	/>

	<!-- Drop Zone -->
	<Card.Content class="p-2">
		<div
			role="button"
			tabindex="0"
			ondragover={handleDragOver}
			ondragleave={handleDragLeave}
			ondrop={handleDrop}
			onclick={handleUploadClick}
			onkeydown={(e) => e.key === 'Enter' && handleUploadClick()}
			class={cn(
				'flex min-h-[90px] cursor-pointer items-center justify-center rounded-lg transition-colors',
				isDragging ? 'bg-muted' : files.length > 0 ? 'bg-muted' : 'bg-muted/50 hover:bg-muted'
			)}
		>
			{#if files.length > 0}
				<div class="flex w-full flex-col gap-1 px-3 py-2">
					{#each files as file, i (file.name + file.size)}
						<div class="flex items-center gap-2">
							<span class="max-w-[200px] truncate text-sm text-foreground">
								{file.name}
							</span>
							<span class="text-xs text-muted-foreground">{formatSize(file.size)}</span>
							<Button
								variant="ghost"
								size="icon"
								class="ml-auto h-6 w-6 cursor-pointer text-muted-foreground hover:text-destructive"
								onclick={(e) => {
									e.stopPropagation();
									handleRemoveFile(i);
								}}
							>
								<X class="h-4 w-4" />
							</Button>
						</div>
					{/each}
				</div>
			{:else}
				<span class="text-sm text-muted-foreground"> Drop files here </span>
			{/if}
		</div>
	</Card.Content>

	<!-- Footer Bar -->
	<Card.Footer class="flex items-center justify-between px-3 py-3">
		<div class="flex items-center gap-2">
			<Button
				variant="ghost"
				size="icon"
				class="h-10 w-10 rounded-full cursor-pointer text-muted-foreground hover:text-foreground"
				onclick={handleUploadClick}
			>
				<Upload class="h-5 w-5" />
			</Button>
			{#if files.length > 1}
				<Button
					variant="ghost"
					size="sm"
					class="h-8 cursor-pointer text-xs text-muted-foreground hover:text-destructive"
					onclick={handleClearAll}
				>
					Clear all ({files.length})
				</Button>
			{/if}
		</div>
		<Button
			size="icon"
			class={cn(
				'h-10 w-10 rounded-full transition-colors',
				files.length > 0
					? 'cursor-pointer bg-primary text-primary-foreground hover:bg-primary/90'
					: 'cursor-not-allowed bg-muted text-muted-foreground'
			)}
			disabled={files.length === 0}
			onclick={handleSubmit}
		>
			<ArrowUp class="h-5 w-5" />
		</Button>
	</Card.Footer>
</Card.Root>
