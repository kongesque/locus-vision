<script lang="ts">
	import { enhance } from '$app/forms';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';

	interface Props {
		data: any;
		form: any;
		loading: string;
	}

	let { data, form, loading = $bindable() }: Props = $props();
</script>

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
