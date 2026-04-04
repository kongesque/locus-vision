<script lang="ts">
	import { enhance } from '$app/forms';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Switch } from '$lib/components/ui/switch/index.js';
	import { Badge } from '$lib/components/ui/badge/index.js';
	import * as Table from '$lib/components/ui/table/index.js';
	import * as AlertDialog from '$lib/components/ui/alert-dialog/index.js';
	import * as Select from '$lib/components/ui/select/index.js';
	import { AlertTriangle, Database } from '@lucide/svelte';

	interface Props {
		data: any;
		form: any;
		loading: string;
	}

	let { data, form, loading = $bindable() }: Props = $props();

	let defaultModelForm = $state<HTMLFormElement>();

	// Delete user confirmation
	let deleteUserId = $state<number | null>(null);
	let deleteUserName = $state('');
	let deleteUserConfirmText = $state('');

	// Delete all media confirmation
	let deleteAllMediaDialog = $state(false);
	let deleteMediaConfirmText = $state('');
</script>

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

		<!-- Default Model Selector -->
		<form
			bind:this={defaultModelForm}
			method="POST"
			action="?/setDefaultModel"
			use:enhance={() => {
				loading = 'defaultModel';
				return async ({ update }) => {
					loading = '';
					await update();
				};
			}}
		>
			<div class="mt-4 flex items-center justify-between rounded-lg border p-4">
				<div class="space-y-0.5">
					<Label for="default_model_select" class="text-sm font-medium">
						Default Model
					</Label>
					<p class="text-sm text-muted-foreground">
						Model pre-selected when creating new tasks
					</p>
				</div>
				<div class="flex items-center gap-2">
					<Select.Root
						type="single"
						name="default_model"
						value={data.appSettings?.default_model ?? 'yolo11n'}
						onValueChange={() => {
							setTimeout(() => defaultModelForm?.requestSubmit(), 0);
						}}
					>
						<Select.Trigger class="w-[200px]">
							{data.modelRegistry?.models?.find(
								(m: { name: string; label: string }) =>
									m.name === (data.appSettings?.default_model ?? 'yolo11n')
							)?.label ?? 'Select model'}
						</Select.Trigger>
						<Select.Content>
							{#each data.modelRegistry?.models ?? [] as model (model.name)}
								<Select.Item value={model.name} label={model.label} />
							{/each}
						</Select.Content>
					</Select.Root>
				</div>
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
