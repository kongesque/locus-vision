<script lang="ts">
	import PageTitle2 from '$lib/components/page-title-2.svelte';
	import EchoLoader from '$lib/components/echo-loader.svelte';
</script>

<svelte:head>
	<title>Home · Locus</title>
</svelte:head>

<div class="flex flex-1 flex-col gap-4 p-4">
	<PageTitle2 />
	<div class="flex flex-1 flex-col items-center justify-center gap-6 rounded-xl bg-muted/50">
		<EchoLoader class="size-12" />
		<div class="space-y-2 text-center">
			<h1 class="text-2xl font-bold">Welcome to LocusVision</h1>
			<p class="text-muted-foreground">Dashboard content goes here.</p>
		</div>
	</div>
</div>
