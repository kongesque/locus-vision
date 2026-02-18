<script lang="ts">
	import LivestreamView from '$lib/components/livestream/livestream-view.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>Livestream · Locus</title>
</svelte:head>

<LivestreamView initialGridCols={data.initialGridCols} />
