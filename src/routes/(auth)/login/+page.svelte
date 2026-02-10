<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Eye, EyeOff } from '@lucide/svelte';
	import Echo from '$lib/components/svg/echo.svelte';

	let email = $state('');
	let password = $state('');
	let showPassword = $state(false);
</script>

<div class="flex min-h-svh flex-col">
	<!-- Logo -->
	<div class="p-6">
		<Echo class="size-6" />
	</div>

	<!-- Form centered -->
	<div class="flex flex-1 items-center justify-center pb-20">
		<div class="w-full max-w-md space-y-4">
			<h1 class="text-center text-2xl font-semibold">Sign in to Locus Vision</h1>

			<form class="space-y-4">
				<div class="space-y-1.5">
					<label for="email" class="text-sm font-semibold">Email</label>
					<Input
						id="email"
						type="email"
						placeholder="Enter Your Email"
						bind:value={email}
						class="rounded-none border-0 border-b border-border bg-transparent px-0 shadow-none placeholder:text-muted-foreground focus-visible:border-foreground focus-visible:ring-0"
					/>
				</div>

				<div class="space-y-1.5">
					<label for="password" class="text-sm font-semibold">Password</label>
					<div class="relative">
						<Input
							id="password"
							type={showPassword ? 'text' : 'password'}
							placeholder="Enter Your Password"
							bind:value={password}
							class="rounded-none border-0 border-b border-border bg-transparent px-0 pr-8 shadow-none placeholder:text-muted-foreground focus-visible:border-foreground focus-visible:ring-0"
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
					Sign in
				</Button>
			</form>

			<p class="text-center text-sm">
				Don't have an account? <a
					href="/signup"
					class="font-medium text-foreground underline hover:text-foreground/80">Sign up</a
				>
			</p>
		</div>
	</div>
</div>
