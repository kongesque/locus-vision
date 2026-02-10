<script lang="ts">
	import EchoLayerInner from './svg/echo-inner.svelte';
	import EchoLayerMiddle from './svg/echo-middle.svelte';
	import EchoLayerOuter from './svg/echo-outer.svelte';
	import { cn } from '$lib/utils.js';

	let { class: className = '', size = 64 } = $props();
</script>

<div class={cn('relative text-primary', className)} style="width: {size}px; height: {size}px;">
	<!-- Layer 1: Core - Static Pulse -->
	<div class="absolute inset-0 flex animate-echo-inner items-center justify-center">
		<EchoLayerInner class="size-full" />
	</div>

	<!-- Layer 2: Middle - Clockwise Breathing -->
	<div class="absolute inset-0 animate-echo-middle">
		<EchoLayerMiddle class="size-full" />
	</div>

	<!-- Layer 3: Outer - Anti-Clockwise Breathing -->
	<div class="absolute inset-0 animate-echo-outer">
		<EchoLayerOuter class="size-full" />
	</div>
</div>
