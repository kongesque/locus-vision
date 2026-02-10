<script lang="ts">
	import { page } from '$app/state';
	import { getPageTitle } from '$lib/utils/page-title.js';

	let { title = undefined } = $props();
	let resolvedTitle = $derived(title ?? getPageTitle(page.url.pathname));
</script>

<span class="text-2xl font-semibold tracking-tight">{resolvedTitle}</span>
