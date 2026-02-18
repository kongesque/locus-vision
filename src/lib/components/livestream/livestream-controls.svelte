<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import ButtonGroup from '$lib/components/ui/button-group/button-group.svelte';
	import { Maximize, Minimize, Minus, Plus } from 'lucide-svelte';
	import { fade } from 'svelte/transition';
	import { onMount } from 'svelte';

	interface LivestreamControlsProps {
		gridCols: number;
		isFullscreen: boolean;
		toggleFullscreen: () => void;
		setGridCols: (cols: number) => void;
	}

	let { gridCols, isFullscreen, toggleFullscreen, setGridCols }: LivestreamControlsProps = $props();

	const HIDE_DELAY_MS = 3000;
	let isHovered = $state(false);
	let isIdle = $state(false);
	let timeoutRef: NodeJS.Timeout | null = null;

	const resetIdleTimer = () => {
		isIdle = false;
		if (timeoutRef) {
			clearTimeout(timeoutRef);
		}
		timeoutRef = setTimeout(() => {
			isIdle = true;
		}, HIDE_DELAY_MS);
	};

	onMount(() => {
		resetIdleTimer();
		window.addEventListener('mousemove', resetIdleTimer);
		return () => {
			if (timeoutRef) clearTimeout(timeoutRef);
			window.removeEventListener('mousemove', resetIdleTimer);
		};
	});

	const handleIncreaseCols = () => {
		setGridCols(Math.min(gridCols + 1, 6));
		resetIdleTimer();
	};

	const handleDecreaseCols = () => {
		setGridCols(Math.max(gridCols - 1, 1));
		resetIdleTimer();
	};

	const handleFullscreenToggle = () => {
		toggleFullscreen();
		resetIdleTimer();
	};
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed right-4 bottom-4 z-20 transition-opacity duration-300"
	class:opacity-0={isIdle && !isHovered}
	class:opacity-100={!isIdle || isHovered}
	onmouseenter={() => {
		isHovered = true;
		resetIdleTimer();
	}}
	onmouseleave={() => {
		isHovered = false;
	}}
>
	<ButtonGroup orientation="horizontal" class="rounded-lg">
		<div class="hidden md:flex">
			<Button
				variant="secondary"
				onclick={handleIncreaseCols}
				disabled={gridCols >= 6}
				title="Increase Columns"
				class="rounded-r-none border-r border-border"
			>
				<Plus />
			</Button>
			<Button
				variant="secondary"
				onclick={handleDecreaseCols}
				disabled={gridCols <= 1}
				title="Decrease Columns"
				class="rounded-l-none"
			>
				<Minus />
			</Button>
		</div>
		<div class="ml-2">
			<Button
				variant="secondary"
				onclick={handleFullscreenToggle}
				title={isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
			>
				{#if isFullscreen}
					<Minimize />
				{:else}
					<Maximize />
				{/if}
			</Button>
		</div>
	</ButtonGroup>
</div>
