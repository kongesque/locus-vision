<script lang="ts">
	import PageTitle2 from '$lib/components/page-title-2.svelte';
	import ModelLibrary from '$lib/components/settings/model-library.svelte';
	import ProfileTab from '$lib/components/settings/profile-tab.svelte';
	import SecurityTab from '$lib/components/settings/security-tab.svelte';
	import AppearanceTab from '$lib/components/settings/appearance-tab.svelte';
	import AdminTab from '$lib/components/settings/admin-tab.svelte';
	import { User, Shield, Palette, Users, Box } from '@lucide/svelte';

	let { data, form }: { data: any; form: any } = $props();
	let loading = $state('');

	// Tab navigation
	let activeTab = $state('profile');

	const userTabs = [
		{ id: 'profile', label: 'Profile', icon: User },
		{ id: 'security', label: 'Security', icon: Shield },
		{ id: 'appearance', label: 'Appearance', icon: Palette },
		{ id: 'models', label: 'Models', icon: Box }
	];

	const adminTabs = [
		{ id: 'profile', label: 'Profile', icon: User },
		{ id: 'security', label: 'Security', icon: Shield },
		{ id: 'appearance', label: 'Appearance', icon: Palette },
		{ id: 'models', label: 'Models', icon: Box },
		{ id: 'admin', label: 'Admin', icon: Users }
	];

	let tabs = $derived(data.user?.role === 'admin' ? adminTabs : userTabs);
</script>

<svelte:head>
	<title>Settings · Locus</title>
</svelte:head>

<div class="relative flex flex-1 flex-col gap-4 p-4">
	<PageTitle2 />

	<!-- Tab Navigation -->
	<div class="flex gap-1 border-b">
		{#each tabs as tab}
			<button
				class="flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors
					{activeTab === tab.id
					? 'border-b-2 border-primary text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				onclick={() => {
					activeTab = tab.id;
				}}
			>
				<tab.icon class="size-4" />
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- PROFILE TAB -->
	{#if activeTab === 'profile'}
		<ProfileTab {data} {form} bind:loading />
	{/if}

	<!-- SECURITY TAB -->
	{#if activeTab === 'security'}
		<SecurityTab {form} bind:loading />
	{/if}

	<!-- APPEARANCE TAB -->
	{#if activeTab === 'appearance'}
		<AppearanceTab />
	{/if}

	<!-- MODELS TAB -->
	{#if activeTab === 'models'}
		<ModelLibrary
			backends={data.modelRegistry?.backends ?? []}
			models={data.modelRegistry?.models ?? []}
		/>
	{/if}

	<!-- ADMIN TAB -->
	{#if activeTab === 'admin' && data.user?.role === 'admin'}
		<AdminTab {data} {form} bind:loading />
	{/if}
</div>
