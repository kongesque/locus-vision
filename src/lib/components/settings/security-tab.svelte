<script lang="ts">
	import { enhance } from '$app/forms';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import * as AlertDialog from '$lib/components/ui/alert-dialog/index.js';
	import { AlertTriangle, LogOut } from '@lucide/svelte';

	interface Props {
		form: any;
		loading: string;
	}

	let { form, loading = $bindable() }: Props = $props();

	// Sign out all devices confirmation
	let signOutAllDialog = $state(false);

	// Delete own account confirmation
	let deleteAccountDialog = $state(false);
	let deleteAccountConfirmText = $state('');
</script>

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
