<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Eye, EyeOff } from '@lucide/svelte';
	import Echo from '$lib/components/svg/echo.svelte';

	let name = $state('');
	let email = $state('');
	let password = $state('');
	let showPassword = $state(false);
</script>

<svelte:head>
	<title>Sign Up · Locus</title>
</svelte:head>

<div class="flex min-h-svh flex-col">
	<!-- Logo -->
	<div class="p-6">
		<Echo class="size-6" />
	</div>

	<!-- Form centered -->
	<div class="flex flex-1 items-center justify-center px-6 pb-20">
		<div class="w-full max-w-md space-y-4">
			<h1 class="text-center text-2xl font-semibold">Get started with Locus Vision</h1>

			<form class="space-y-4">
				<div>
					<label for="name" class="text-sm font-semibold">Name</label>
					<Input
						id="name"
						type="text"
						placeholder="Enter Your Full Name"
						bind:value={name}
						class="rounded-none border-0 border-b border-border bg-transparent px-0 shadow-none placeholder:text-muted-foreground focus-visible:border-foreground focus-visible:ring-0 dark:bg-transparent"
					/>
				</div>

				<div>
					<label for="email" class="text-sm font-semibold">Email</label>
					<Input
						id="email"
						type="email"
						placeholder="Enter Your Email"
						bind:value={email}
						class="rounded-none border-0 border-b border-border bg-transparent px-0 shadow-none placeholder:text-muted-foreground focus-visible:border-foreground focus-visible:ring-0 dark:bg-transparent"
					/>
				</div>

				<div>
					<label for="password" class="text-sm font-semibold">Password</label>
					<div class="relative">
						<Input
							id="password"
							type={showPassword ? 'text' : 'password'}
							placeholder="Enter Your Password"
							bind:value={password}
							class="rounded-none border-0 border-b border-border bg-transparent px-0 pr-8 shadow-none placeholder:text-muted-foreground focus-visible:border-foreground focus-visible:ring-0 dark:bg-transparent"
						/>
						<button
							type="button"
							class="absolute top-1/2 right-0 -translate-y-1/2 text-muted-foreground hover:text-foreground"
							onclick={() => (showPassword = !showPassword)}
						>
							{#if showPassword}
								<Eye class="size-4" />
							{:else}
								<EyeOff class="size-4" />
							{/if}
						</button>
					</div>
				</div>

				<Button
					type="submit"
					class="w-full rounded-full bg-muted text-foreground shadow-none hover:bg-muted/80"
				>
					Create Admin Account
				</Button>
			</form>
		</div>
	</div>
</div>
