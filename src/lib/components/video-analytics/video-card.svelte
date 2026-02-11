<script lang="ts">
	import * as Card from '$lib/components/ui/card/index.js';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import { Download, MoreVertical, Trash2 } from '@lucide/svelte';

	interface Props {
		taskId: string;
		name: string;
		thumbnail?: string;
		duration: string;
		createdAt: string;
		format: string;
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
		onDownload,
		onDelete
	}: Props = $props();
</script>

<Card.Root class="group w-full gap-0 border-0 bg-transparent py-2 shadow-none ring-0">
	<!-- Thumbnail container with timestamp -->
	<a href={`/video-analytics/${taskId}`}>
		<div
			class="relative cursor-pointer overflow-hidden rounded-xl transition-all duration-300 group-hover:rounded-none"
		>
			<img
				src={thumbnail}
				alt={name}
				class="aspect-video w-full object-cover transition-opacity duration-300 group-hover:opacity-50"
			/>
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
