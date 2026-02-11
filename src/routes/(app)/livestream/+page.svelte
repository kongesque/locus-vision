<script lang="ts">
	import PageTitle2 from '$lib/components/page-title-2.svelte';
	import AddCamera from '$lib/components/livestream/add-camera.svelte';
</script>

<svelte:head>
	<title>Livestream · Locus</title>
</svelte:head>

<div class="flex flex-1 flex-col gap-4 p-4">
	<div class="flex items-center justify-between">
		<PageTitle2 />
		<AddCamera />
	</div>
	<div class="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl bg-muted/50">
		<h3 class="text-md font-medium text-muted-foreground">No Cameras</h3>
		<p class="text-sm text-muted-foreground">
			Add your first camera by clicking on the plus button above.
		</p>
	</div>
</div>
