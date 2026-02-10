<script lang="ts">
	import { goto } from '$app/navigation';
	import { Upload, ArrowUp, X } from '@lucide/svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { videoStore } from '$lib/stores/video.svelte.js';
	import { cn } from '$lib/utils.js';

	let file = $state<File | null>(null);
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
		const droppedFile = e.dataTransfer?.files[0];
		if (droppedFile) {
			file = droppedFile;
		}
	};

	const handleFileSelect = (e: Event) => {
		const target = e.target as HTMLInputElement;
		const selectedFile = target.files?.[0];
		if (selectedFile) {
			file = selectedFile;
		}
	};

	const handleUploadClick = () => {
		fileInputRef?.click();
	};

	const handleRemoveFile = () => {
		file = null;
		if (fileInputRef) {
			fileInputRef.value = '';
		}
	};

	const handleSubmit = async () => {
		if (!file) return;

		const taskId = crypto.randomUUID();
		const objectUrl = URL.createObjectURL(file);

		videoStore.setVideoUrl(objectUrl);
		videoStore.setVideoType('file');

		goto(`/create/${taskId}`);
	};
</script>

<Card.Root class="w-full gap-0 p-0">
	<!-- Hidden File Input -->
	<input
		bind:this={fileInputRef}
		type="file"
		accept="video/*"
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
				isDragging ? 'bg-muted' : file ? 'bg-muted' : 'bg-muted/50 hover:bg-muted'
			)}
		>
			{#if file}
				<div class="flex items-center gap-2 px-3">
					<span class="max-w-[200px] truncate text-sm text-foreground">
						{file.name}
					</span>
					<Button
						variant="ghost"
						size="icon"
						class="h-6 w-6 cursor-pointer text-muted-foreground hover:text-destructive"
						onclick={(e) => {
							e.stopPropagation();
							handleRemoveFile();
						}}
					>
						<X class="h-4 w-4" />
					</Button>
				</div>
			{:else}
				<span class="text-sm text-muted-foreground"> Drop files here </span>
			{/if}
		</div>
	</Card.Content>

	<!-- Footer Bar -->
	<Card.Footer class="flex items-center justify-between px-3 py-3">
		<Button
			variant="ghost"
			size="icon"
			class="h-10 w-10 rounded-full text-muted-foreground hover:text-foreground"
			onclick={handleUploadClick}
		>
			<Upload class="h-5 w-5" />
		</Button>
		<Button
			size="icon"
			class={cn(
				'h-10 w-10 rounded-full transition-colors',
				file
					? 'cursor-pointer bg-primary text-primary-foreground hover:bg-primary/90'
					: 'cursor-not-allowed bg-muted text-muted-foreground'
			)}
			disabled={!file}
			onclick={handleSubmit}
		>
			<ArrowUp class="h-5 w-5" />
		</Button>
	</Card.Footer>
</Card.Root>
