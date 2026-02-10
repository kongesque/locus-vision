<script lang="ts">
	import { page } from '$app/state';
	import { getPageTitle } from '$lib/utils/page-title.js';

	let title = $derived(getPageTitle(page.url.pathname));
</script>

<span class="text-sm font-medium">{title}</span>
