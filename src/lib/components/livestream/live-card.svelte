<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import { API_URL } from '$lib/api';
	import { fade } from 'svelte/transition';
	import EchoLoader from '$lib/components/echo-loader.svelte';
	import { CircleAlert } from '@lucide/svelte';

	interface LiveCardProps {
		cameraId: string;
		title?: string;
		thumbnail?: string;
		status?: 'live' | 'offline' | 'connecting';
		cameraName?: string;
		size?: 'sm' | 'md' | 'lg';
	}

	let {
		cameraId,
		title = 'Live Stream',
		thumbnail = '/locus.png',
		status = 'live',
		cameraName = 'Camera 1',
		size = 'md'
	}: LiveCardProps = $props();

	let currentTime = $state(new Date());

	onMount(() => {
		const timer = setInterval(() => {
			currentTime = new Date();
		}, 1000);

		return () => clearInterval(timer);
	});

	const formatDate = (date: Date) => {
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: '2-digit',
			day: '2-digit'
		});
	};

	const formatTime = (date: Date) => {
		return date.toLocaleTimeString('en-US', {
			hour: '2-digit',
			minute: '2-digit',
			second: '2-digit',
			hour12: false
		});
	};

	// Size-based classes
	const textSize = {
		sm: 'text-[10px]',
		md: 'text-xs',
		lg: 'text-sm'
	};

	const iconSize = {
		sm: 'size-1',
		md: 'size-2',
		lg: 'size-3'
	};

	const loaderSize = {
		sm: 32,
		md: 48,
		lg: 64
	};

	const camPos = {
		sm: '-top-1 left-1',
		md: 'top-1 left-2',
		lg: 'top-2 left-3'
	};

	const timePos = {
		sm: '-bottom-1 left-1',
		md: 'bottom-1 left-2',
		lg: 'bottom-3 left-3'
	};
</script>

<!-- Mock link to UI -->
<a href={`/livestream/${cameraId}`} class="group block w-full">
	<!-- Thumbnail container with CCTV overlay -->
	<div
		class="relative cursor-pointer overflow-hidden rounded-xl transition-all duration-300 group-hover:rounded-none"
	>
		<img
			src={`${API_URL}/api/livestream/${cameraId}/video`}
			alt={title}
			class="aspect-video w-full object-cover transition-opacity duration-300 group-hover:opacity-80"
		/>

		<!-- Camera name badge - top left -->
		<div class={`absolute ${camPos[size]} z-10`}>
			<span class={`font-mono text-white/70 ${textSize[size]}`}>
				{cameraName}
			</span>
		</div>

		<!-- Live status indicator - top right -->
		{#if status === 'live'}
			<div class="absolute top-2 right-2 z-10">
				<span class={`relative flex ${iconSize[size]}`}>
					<span class={`inline-flex animate-pulse rounded-full bg-red-500 ${iconSize[size]}`}
					></span>
				</span>
			</div>
		{/if}

		<!-- Connecting overlay -->
		{#if status === 'connecting'}
			<div
				class="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/70"
				transition:fade
			>
				<EchoLoader size={loaderSize[size]} class="text-white/80" />
				<span class={`animate-pulse font-medium text-white/80 ${textSize[size]}`}
					>Connecting...</span
				>
			</div>
		{/if}

		<!-- Offline overlay -->
		{#if status === 'offline'}
			<div
				class="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-black/70"
				transition:fade
			>
				<CircleAlert class={`text-white/80 size-${loaderSize[size] / 4}`} />
				<!-- approximate size conversion for lucide -->
				<span class={`font-medium text-white/80 ${textSize[size]}`}>Offline</span>
			</div>
		{/if}

		<!-- Date & Time overlay - bottom left (hidden when offline) -->
		{#if status !== 'offline' && currentTime}
			<div class={`absolute ${timePos[size]} z-10`}>
				<span class={`font-mono text-white/70 ${textSize[size]}`}>
					{formatDate(currentTime)}
					{formatTime(currentTime)}
				</span>
			</div>
		{/if}
	</div>
</a>
