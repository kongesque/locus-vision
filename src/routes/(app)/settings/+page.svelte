<script lang="ts">
	import { enhance } from '$app/forms';
	import PageTitle2 from '$lib/components/page-title-2.svelte';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Separator } from '$lib/components/ui/separator/index.js';
	import { Switch } from '$lib/components/ui/switch/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as AlertDialog from '$lib/components/ui/alert-dialog/index.js';
	import { User, Shield, Palette, Users, Database, LogOut, AlertTriangle } from '@lucide/svelte';
	import { setMode, resetMode } from 'mode-watcher';

	let { data, form }: { data: any; form: any } = $props();
	let loading = $state('');

	// Tab navigation
	let activeTab = $state('profile');

	const userTabs = [
		{ id: 'profile', label: 'Profile', icon: User },
		{ id: 'security', label: 'Security', icon: Shield },
		{ id: 'appearance', label: 'Appearance', icon: Palette }
	];

	const adminTabs = [
		{ id: 'profile', label: 'Profile', icon: User },
		{ id: 'security', label: 'Security', icon: Shield },
		{ id: 'appearance', label: 'Appearance', icon: Palette },
		{ id: 'admin', label: 'Admin', icon: Users }
	];

	let tabs = $derived(data.user?.role === 'admin' ? adminTabs : userTabs);

	// Delete user confirmation
	let deleteUserId = $state<number | null>(null);
	let deleteUserName = $state('');
	let deleteUserConfirmText = $state('');

	// Delete all media confirmation
	let deleteAllMediaDialog = $state(false);
	let deleteMediaConfirmText = $state('');

	// Delete own account confirmation
	let deleteAccountDialog = $state(false);
	let deleteAccountConfirmText = $state('');

	// Sign out all devices confirmation
	let signOutAllDialog = $state(false);
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
				onclick={() => (activeTab = tab.id)}
			>
				<tab.icon class="size-4" />
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- PROFILE TAB -->
	{#if activeTab === 'profile'}
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg">Profile</Card.Title>
				<Card.Description>Manage your profile information</Card.Description>
			</Card.Header>
			<Card.Content>
				<form
					method="POST"
					action="?/updateAccount"
					use:enhance={() => {
						loading = 'account';
						return async ({ update }) => {
							loading = '';
							await update();
						};
					}}
					class="space-y-4"
				>
					<div class="grid gap-4 sm:grid-cols-2">
						<div class="space-y-2">
							<Label for="name">Name</Label>
							<Input id="name" name="name" value={data.user?.name ?? ''} placeholder="Your name" />
						</div>
						<div class="space-y-2">
							<Label for="email">Email</Label>
							<Input
								id="email"
								name="email"
								type="email"
								value={data.user?.email ?? ''}
								placeholder="you@example.com"
							/>
						</div>
					</div>

					{#if form?.accountError}
						<p class="text-sm text-destructive">{form.accountError}</p>
					{/if}
					{#if form?.accountSuccess}
						<p class="text-sm text-green-600">Account updated successfully</p>
					{/if}

					<div class="flex justify-end pt-4">
						<Button type="submit" disabled={loading === 'account'}>
							{loading === 'account' ? 'Saving…' : 'Save Changes'}
						</Button>
					</div>
				</form>

				<div class="mt-6 flex flex-col gap-4 border-t pt-4">
					<div class="flex items-center justify-between">
						<div class="space-y-0.5">
							<Label class="text-sm font-medium">Sign Out</Label>
							<p class="text-xs text-muted-foreground">Log out of your account on this device.</p>
						</div>
						<form method="POST" action="/logout">
							<Button type="submit" variant="outline" size="sm">Log Out</Button>
						</form>
					</div>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- SECURITY TAB -->
	{#if activeTab === 'security'}
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg">Change Password</Card.Title>
				<Card.Description>Update your password to keep your account secure</Card.Description>
			</Card.Header>
			<Card.Content>
				<form
					method="POST"
					action="?/changePassword"
					use:enhance={() => {
						loading = 'password';
						return async ({ update }) => {
							loading = '';
							await update();
						};
					}}
					class="space-y-4"
				>
					<div class="space-y-2">
						<Label for="current_password">Current Password</Label>
						<Input
							id="current_password"
							name="current_password"
							type="password"
							placeholder="Enter current password"
							autocomplete="current-password"
						/>
					</div>
					<div class="grid gap-4 sm:grid-cols-2">
						<div class="space-y-2">
							<Label for="new_password">New Password</Label>
							<Input
								id="new_password"
								name="new_password"
								type="password"
								placeholder="Minimum 8 characters"
								autocomplete="new-password"
							/>
						</div>
						<div class="space-y-2">
							<Label for="confirm_password">Confirm New Password</Label>
							<Input
								id="confirm_password"
								name="confirm_password"
								type="password"
								placeholder="Repeat new password"
								autocomplete="new-password"
							/>
						</div>
					</div>

					{#if form?.passwordError}
						<p class="text-sm text-destructive">{form.passwordError}</p>
					{/if}

					<div class="flex justify-end">
						<Button type="submit" disabled={loading === 'password'}>
							{loading === 'password' ? 'Changing…' : 'Change Password'}
						</Button>
					</div>
				</form>
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg">Sessions</Card.Title>
				<Card.Description>Manage your active sessions across devices</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
					<div class="space-y-0.5">
						<div class="flex items-center gap-2">
							<LogOut class="size-4 text-muted-foreground" />
							<Label class="text-sm font-medium">Sign Out of All Devices</Label>
						</div>
						<p class="text-xs text-muted-foreground">
							Revoke all active sessions. You will need to log in again on every device.
						</p>
					</div>
					<Button variant="outline" size="sm" onclick={() => (signOutAllDialog = true)}>
						Sign Out Everywhere
					</Button>
				</div>
			</Card.Content>
		</Card.Root>

		<Card.Root class="border-destructive/50 bg-destructive/5">
			<Card.Header>
				<div class="flex items-center gap-2">
					<AlertTriangle class="size-5 text-destructive" />
					<Card.Title class="text-lg text-destructive">Danger Zone</Card.Title>
				</div>
				<Card.Description class="text-destructive/80">
					Destructive actions that cannot be undone. Proceed with caution.
				</Card.Description>
			</Card.Header>
			<Card.Content class="space-y-4">
				<div
					class="flex items-center justify-between rounded-lg border border-destructive/20 bg-background p-4"
				>
					<div class="space-y-0.5">
						<p class="font-medium">Delete Account</p>
						<p class="text-sm text-muted-foreground">
							Permanently delete your account and all associated data.
						</p>
					</div>
					<Button variant="destructive" size="sm" onclick={() => (deleteAccountDialog = true)}>
						Delete Account
					</Button>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- APPEARANCE TAB -->
	{#if activeTab === 'appearance'}
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg">Theme</Card.Title>
				<Card.Description>Customize the appearance of the application</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="flex flex-wrap items-center gap-3">
					<Button
						variant="outline"
						class="flex items-center gap-2"
						onclick={() => setMode('light')}
					>
						<svg
							class="size-4"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
						>
							<circle cx="12" cy="12" r="4" />
							<path
								d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"
							/>
						</svg>
						Light
					</Button>
					<Button variant="outline" class="flex items-center gap-2" onclick={() => setMode('dark')}>
						<svg
							class="size-4"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
						>
							<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />
						</svg>
						Dark
					</Button>
					<Button variant="outline" class="flex items-center gap-2" onclick={() => resetMode()}>
						<svg
							class="size-4"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
						>
							<rect width="20" height="14" x="2" y="3" rx="2" />
							<line x1="8" x2="16" y1="21" y2="21" />
							<line x1="12" x2="12" y1="17" y2="21" />
						</svg>
						System
					</Button>
				</div>
			</Card.Content>
		</Card.Root>
	{/if}

	<!-- ADMIN TAB -->
	{#if activeTab === 'admin' && data.user?.role === 'admin'}
		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg">App Settings</Card.Title>
				<Card.Description>Configure application-level settings</Card.Description>
			</Card.Header>
			<Card.Content>
				<form
					method="POST"
					action="?/toggleSignup"
					use:enhance={() => {
						loading = 'signup';
						return async ({ update }) => {
							loading = '';
							await update();
						};
					}}
				>
					<div class="flex items-center justify-between rounded-lg border p-4">
						<div class="space-y-0.5">
							<Label for="allow_signup_toggle" class="text-sm font-medium">
								Allow Public Signup
							</Label>
							<p class="text-sm text-muted-foreground">
								When enabled, anyone can create an account
							</p>
						</div>
						<input
							type="hidden"
							name="allow_signup"
							value={data.appSettings?.allow_signup ? 'false' : 'true'}
						/>
						<Button
							type="submit"
							variant="ghost"
							size="sm"
							class="h-auto p-0 hover:bg-transparent"
							disabled={loading === 'signup'}
						>
							<Switch
								checked={data.appSettings?.allow_signup ?? false}
								id="allow_signup_toggle"
								aria-label="Toggle public signup"
							/>
						</Button>
					</div>
				</form>

				{#if form?.settingsSuccess}
					<p class="mt-2 text-sm text-green-600">Settings updated</p>
				{/if}
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg text-destructive">Data Management</Card.Title>
				<Card.Description>Manage application data and media files</Card.Description>
			</Card.Header>
			<Card.Content>
				<div class="mb-4 space-y-2 rounded-lg bg-muted p-4 text-sm">
					<div class="flex items-center gap-2 font-medium text-amber-500">
						<Database class="size-4" />
						Automated Analytics Retention
					</div>
					<p class="text-muted-foreground">
						Time-series analytics telemetry and tracking arrays from the DuckDB cache are
						automatically compressed and offloaded to Cold Storage Parquet Arrays by the background
						Archiver service to preserve local SSD tier storage. You do not need to manually delete
						this data.
					</p>
				</div>

				<!-- Storage Metrics Link -->
				<a
					href="/system"
					class="mb-4 flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-muted"
				>
					<div class="space-y-0.5">
						<Label class="cursor-pointer text-sm font-medium">Storage Metrics</Label>
						<p class="text-sm text-muted-foreground">
							View disk usage, recordings, and database sizes
						</p>
					</div>
					<span class="text-muted-foreground">→</span>
				</a>

				<div class="flex items-center justify-between rounded-lg border border-destructive/20 p-4">
					<div class="space-y-0.5">
						<Label class="text-sm font-medium">Clear All Media</Label>
						<p class="text-sm text-muted-foreground">
							Permanently delete all videos, tasks, and camera stream configurations
						</p>
					</div>
					<Button variant="destructive" size="sm" onclick={() => (deleteAllMediaDialog = true)}>
						Clear Media
					</Button>
				</div>
				{#if form?.adminSuccess && form?.message}
					<p class="mt-4 text-sm text-green-600">{form.message}</p>
				{/if}
			</Card.Content>
		</Card.Root>

		<Card.Root>
			<Card.Header>
				<Card.Title class="text-lg">User Management</Card.Title>
				<Card.Description>
					{data.users?.length ?? 0} registered user{(data.users?.length ?? 0) !== 1 ? 's' : ''}
				</Card.Description>
			</Card.Header>
			<Card.Content>
				{#if form?.adminError}
					<p class="mb-4 text-sm text-destructive">{form.adminError}</p>
				{/if}
				{#if form?.adminSuccess}
					<p class="mb-4 text-sm text-green-600">Updated successfully</p>
				{/if}

				<Table.Root>
					<Table.Header>
						<Table.Row>
							<Table.Head>User</Table.Head>
							<Table.Head>Role</Table.Head>
							<Table.Head>Status</Table.Head>
							<Table.Head class="text-right">Actions</Table.Head>
						</Table.Row>
					</Table.Header>
					<Table.Body>
						{#each data.users ?? [] as user}
							<Table.Row>
								<Table.Cell>
									<div>
										<p class="font-medium">{user.name}</p>
										<p class="text-sm text-muted-foreground">{user.email}</p>
									</div>
								</Table.Cell>
								<Table.Cell>
									{#if user.id === data.user?.id}
										<Badge variant="default">{user.role}</Badge>
									{:else}
										<form method="POST" action="?/updateRole" use:enhance class="inline">
											<input type="hidden" name="user_id" value={user.id} />
											<input
												type="hidden"
												name="role"
												value={user.role === 'admin' ? 'viewer' : 'admin'}
											/>
											<Button
												type="submit"
												variant="ghost"
												size="sm"
												class="h-auto p-0 hover:bg-transparent"
											>
												<Badge
													variant={user.role === 'admin' ? 'default' : 'secondary'}
													class="cursor-pointer"
												>
													{user.role}
												</Badge>
											</Button>
										</form>
									{/if}
								</Table.Cell>
								<Table.Cell>
									{#if user.id === data.user?.id}
										<Badge variant="outline" class="border-green-600 text-green-600">Active</Badge>
									{:else}
										<form method="POST" action="?/toggleUserActive" use:enhance class="inline">
											<input type="hidden" name="user_id" value={user.id} />
											<Button
												type="submit"
												variant="ghost"
												size="sm"
												class="h-auto p-0 hover:bg-transparent"
											>
												<Badge
													variant="outline"
													class={user.is_active
														? 'cursor-pointer border-green-600 text-green-600'
														: 'cursor-pointer border-red-500 text-red-500'}
												>
													{user.is_active ? 'Active' : 'Inactive'}
												</Badge>
											</Button>
										</form>
									{/if}
								</Table.Cell>
								<Table.Cell class="text-right">
									{#if user.id !== data.user?.id}
										<Button
											variant="ghost"
											size="sm"
											class="text-destructive hover:text-destructive"
											onclick={() => {
												deleteUserId = user.id;
												deleteUserName = user.name;
											}}
										>
											Delete
										</Button>
									{:else}
										<span class="text-sm text-muted-foreground">You</span>
									{/if}
								</Table.Cell>
							</Table.Row>
						{/each}
					</Table.Body>
				</Table.Root>
			</Card.Content>
		</Card.Root>
	{/if}
</div>

<!-- Delete User Confirmation Dialog -->
<AlertDialog.Root
	open={deleteUserId !== null}
	onOpenChange={(open) => {
		if (!open) {
			deleteUserId = null;
			deleteUserConfirmText = '';
		}
	}}
>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title class="flex items-center gap-2">
				<AlertTriangle class="size-5 text-destructive" />
				Delete User
			</AlertDialog.Title>
			<AlertDialog.Description>
				Are you sure you want to delete <strong>{deleteUserName}</strong>? This action cannot be
				undone. All their data and sessions will be permanently removed.
			</AlertDialog.Description>
		</AlertDialog.Header>
		<div class="py-4">
			<Label for="confirm-delete-user" class="text-sm font-medium">
				Type <code class="rounded bg-muted px-1">DELETE</code> to confirm
			</Label>
			<Input
				id="confirm-delete-user"
				type="text"
				placeholder="Type DELETE to confirm"
				bind:value={deleteUserConfirmText}
				class="mt-2"
			/>
		</div>
		<AlertDialog.Footer>
			<AlertDialog.Cancel
				onclick={() => {
					deleteUserId = null;
					deleteUserConfirmText = '';
				}}
			>
				Cancel
			</AlertDialog.Cancel>
			<form method="POST" action="?/deleteUser" use:enhance class="inline">
				<input type="hidden" name="user_id" value={deleteUserId} />
				<Button type="submit" variant="destructive" disabled={deleteUserConfirmText !== 'DELETE'}>
					Delete User
				</Button>
			</form>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>

<!-- Delete All Media Confirmation Dialog -->
<AlertDialog.Root
	open={deleteAllMediaDialog}
	onOpenChange={(open) => {
		if (!open) {
			deleteAllMediaDialog = false;
			deleteMediaConfirmText = '';
		}
	}}
>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title class="flex items-center gap-2">
				<AlertTriangle class="size-5 text-destructive" />
				Delete All Media
			</AlertDialog.Title>
			<AlertDialog.Description>
				Are you sure you want to delete all videos, processing tasks, and camera configurations?
				This action cannot be undone and all physical media files will be permanently removed.
			</AlertDialog.Description>
		</AlertDialog.Header>
		<div class="py-4">
			<Label for="confirm-delete-media" class="text-sm font-medium">
				Type <code class="rounded bg-muted px-1">DELETE</code> to confirm
			</Label>
			<Input
				id="confirm-delete-media"
				type="text"
				placeholder="Type DELETE to confirm"
				bind:value={deleteMediaConfirmText}
				class="mt-2"
			/>
		</div>
		<AlertDialog.Footer>
			<AlertDialog.Cancel
				onclick={() => {
					deleteAllMediaDialog = false;
					deleteMediaConfirmText = '';
				}}
			>
				Cancel
			</AlertDialog.Cancel>
			<form method="POST" action="?/deleteAllMedia"
				use:enhance={() => {
					return async ({ update }) => {
						await update();
						deleteAllMediaDialog = false;
						deleteMediaConfirmText = '';
					};
				}}
				class="inline"
			>
				<Button
					type="submit"
					variant="destructive"
					disabled={deleteMediaConfirmText !== 'DELETE'}
				>
					Delete All
				</Button>
			</form>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>

<!-- Delete Own Account Confirmation Dialog -->
<AlertDialog.Root
	open={deleteAccountDialog}
	onOpenChange={(open) => {
		if (!open) {
			deleteAccountDialog = false;
			deleteAccountConfirmText = '';
		}
	}}
>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title class="flex items-center gap-2">
				<AlertTriangle class="size-5 text-destructive" />
				Delete Account
			</AlertDialog.Title>
			<AlertDialog.Description>
				Are you sure you want to delete your account? This action cannot be undone and you will lose
				access immediately. All your data will be permanently removed.
			</AlertDialog.Description>
		</AlertDialog.Header>
		<div class="py-4">
			<Label for="confirm-delete-account" class="text-sm font-medium">
				Type <code class="rounded bg-muted px-1">DELETE</code> to confirm
			</Label>
			<Input
				id="confirm-delete-account"
				type="text"
				placeholder="Type DELETE to confirm"
				bind:value={deleteAccountConfirmText}
				class="mt-2"
			/>
		</div>
		<AlertDialog.Footer>
			<AlertDialog.Cancel
				onclick={() => {
					deleteAccountDialog = false;
					deleteAccountConfirmText = '';
				}}
			>
				Cancel
			</AlertDialog.Cancel>
			<form method="POST" action="?/deleteAccount" use:enhance class="inline">
				<Button
					type="submit"
					variant="destructive"
					disabled={deleteAccountConfirmText !== 'DELETE'}
					onclick={() => {
						deleteAccountDialog = false;
						deleteAccountConfirmText = '';
					}}
				>
					Delete My Account
				</Button>
			</form>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>

<!-- Sign Out All Devices Confirmation Dialog -->
<AlertDialog.Root
	open={signOutAllDialog}
	onOpenChange={(open) => {
		if (!open) signOutAllDialog = false;
	}}
>
	<AlertDialog.Content>
		<AlertDialog.Header>
			<AlertDialog.Title>Sign Out of All Devices</AlertDialog.Title>
			<AlertDialog.Description>
				This will revoke all active sessions across every device. You will be signed out immediately
				and will need to log in again.
			</AlertDialog.Description>
		</AlertDialog.Header>
		<AlertDialog.Footer>
			<AlertDialog.Cancel onclick={() => (signOutAllDialog = false)}>Cancel</AlertDialog.Cancel>
			<form method="POST" action="?/revokeSessions" use:enhance class="inline">
				<Button type="submit" variant="destructive" onclick={() => (signOutAllDialog = false)}
					>Sign Out Everywhere</Button
				>
			</form>
		</AlertDialog.Footer>
	</AlertDialog.Content>
</AlertDialog.Root>
