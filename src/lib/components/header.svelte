<script lang="ts">
	import { SidebarTrigger } from '$lib/components/ui/sidebar/index.js';
	import { cn } from '$lib/utils.js';
	import PageTitle from '$lib/components/page-title.svelte';
	import { Button } from '$lib/components/ui/button/index.js';

	let {
		class: className = undefined,
		cursorClass = undefined
	}: {
		class?: string;
		cursorClass?: string;
	} = $props();
</script>

<header
	class={cn(
		'sticky top-0 z-20 flex h-12 shrink-0 items-center justify-between border-b bg-background px-4',
		className
	)}
>
	<div class="flex items-center gap-4">
		<SidebarTrigger class={cn('-ml-2.5', cursorClass)} />
		<PageTitle />
	</div>
	<div class="flex items-center gap-2">
		<Button
			variant="outline"
			size="sm"
			href="https://www.kongesque.com"
			target="_blank"
			rel="noopener noreferrer"
		>
			Docs
		</Button>
	</div>
</header>
