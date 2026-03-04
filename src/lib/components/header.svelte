<script lang="ts">
	import { SidebarTrigger } from '$lib/components/ui/sidebar/index.js';
	import { useSidebar } from '$lib/components/ui/sidebar/context.svelte.js';
	import { cn } from '$lib/utils.js';
	import PageTitle from '$lib/components/page-title-1.svelte';
	import { Button } from '$lib/components/ui/button/index.js';

	let {
		class: className = undefined
	}: {
		class?: string;
	} = $props();

	const sidebar = useSidebar();
</script>

<header
	class={cn(
		'sticky top-0 flex h-12 shrink-0 items-center justify-between border-b bg-background px-4',
		className
	)}
>
	<div class="flex items-center gap-4">
		<SidebarTrigger class={cn('-ml-2.5', sidebar.open ? 'cursor-w-resize' : 'cursor-e-resize')} />
		<PageTitle />
	</div>
</header>
