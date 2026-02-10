<script lang="ts">
	import './layout.css';
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import AppSidebar from '$lib/components/app-sidebar.svelte';
	import Header from '$lib/components/header.svelte';

	let { data, children } = $props();
</script>

<Sidebar.Provider open={data.sidebarOpen}>
	<AppSidebar />
	<main class="flex h-svh w-full flex-1 flex-col overflow-y-auto">
		<Header />
		{@render children?.()}
	</main>
</Sidebar.Provider>
