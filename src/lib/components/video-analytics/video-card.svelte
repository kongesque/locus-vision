<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Download, MoreVertical, Trash2, Clock, CheckCircle2, AlertCircle } from '@lucide/svelte';
	import { Badge } from '$lib/components/ui/badge/index.js';

	interface Props {
		taskId: string;
		name: string;
		thumbnail?: string;
		duration: string;
		createdAt: string;
		format: string;
		status?: string;
		onDownload?: () => void;
		onDelete?: () => void;
	}

	let {
		taskId,
		name,
		thumbnail = '/locus.png',
		duration,
		createdAt,
		format,
		status = 'completed',
		onDownload,
		onDelete
	}: Props = $props();

	// Fallback image handling
	let imgFailed = $state(false);

	function handleImgError() {
		imgFailed = true;
	}

	// Reset error state when thumbnail changes
	$effect(() => {
		// Access thumbnail to track dependency
		thumbnail;
		imgFailed = false;
	});

	let finalSrc = $derived(imgFailed ? '/locus.png' : thumbnail);

	let statusColor = $derived(
		status === 'completed'
			? 'bg-green-500/10 text-green-500 hover:bg-green-500/20'
			: status === 'processing'
				? 'bg-blue-500/10 text-blue-500 hover:bg-blue-500/20'
				: status === 'failed'
					? 'bg-red-500/10 text-red-500 hover:bg-red-500/20'
					: 'bg-secondary text-secondary-foreground'
	);
</script>

<Card.Root class="group w-full gap-0 border-0 bg-transparent py-2 shadow-none ring-0">
	<!-- Thumbnail container with timestamp -->
	<a href={`/video-analytics/${taskId}`}>
		<div
			class="relative aspect-video cursor-pointer overflow-hidden rounded-xl bg-muted transition-all duration-300 group-hover:rounded-none"
		>
			<img
				src={finalSrc}
				alt={name}
				class="aspect-video w-full object-cover transition-opacity duration-300 group-hover:opacity-50"
				onerror={handleImgError}
			/>

			<!-- Status Badge (if not completed or just to show status) -->
			<div class="absolute top-2 left-2">
				<Badge variant="outline" class="{statusColor} border-0 backdrop-blur-sm">
					{#if status === 'processing'}
						<Clock class="mr-1 h-3 w-3 animate-pulse" />
						Processing
					{:else if status === 'completed'}
						<CheckCircle2 class="mr-1 h-3 w-3" />
						Done
					{:else if status === 'failed'}
						<AlertCircle class="mr-1 h-3 w-3" />
						Failed
					{:else}
						{status}
					{/if}
				</Badge>
			</div>

			<!-- Timestamp badge -->
			<div class="absolute right-2 bottom-2 rounded bg-black/80 px-1.5 py-0.5 text-xs text-white">
				{duration}
			</div>
		</div>
	</a>

	<!-- Video info -->
	<Card.Header class="px-0 pt-3 pb-0">
		<Card.Title class="text-sm">
			{name}
		</Card.Title>
		<Card.Description class="text-xs">
			{createdAt} • {format}
		</Card.Description>
		<Card.Action>
			<DropdownMenu.Root>
				<DropdownMenu.Trigger>
					{#snippet child({ props })}
						<Button
							{...props}
							variant="ghost"
							size="icon"
							class="h-8 w-8 cursor-pointer focus:outline-none focus-visible:border-transparent focus-visible:ring-0 focus-visible:ring-offset-0 data-[state=open]:bg-accent"
						>
							<MoreVertical class="h-4 w-4" />
							<span class="sr-only">Open menu</span>
						</Button>
					{/snippet}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content align="end">
					<DropdownMenu.Item onclick={onDownload}>
						<Download class="mr-2 h-4 w-4" />
						Download
					</DropdownMenu.Item>
					<DropdownMenu.Item class="text-destructive focus:text-destructive" onclick={onDelete}>
						<Trash2 class="mr-2 h-4 w-4" />
						Delete
					</DropdownMenu.Item>
				</DropdownMenu.Content>
			</DropdownMenu.Root>
		</Card.Action>
	</Card.Header>
</Card.Root>
