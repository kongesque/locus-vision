<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import Echo from '$lib/components/svg/echo.svelte';

	let name = $state('');
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
		<div class="w-full max-w-sm space-y-6">
			<h1 class="text-center text-2xl font-semibold">Sign up to Locus Vision</h1>

			<form class="space-y-4">
				<div class="space-y-1.5">
					<label for="name" class="text-sm font-semibold">Name</label>
					<Input
						id="name"
						type="text"
						placeholder="Enter Your Full Name"
						bind:value={name}
						class="rounded-none border-0 border-b border-border bg-transparent px-0 shadow-none focus-visible:border-foreground focus-visible:ring-0"
					/>
				</div>

				<div class="space-y-1.5">
					<label for="email" class="text-sm font-semibold">Email</label>
					<Input
						id="email"
						type="email"
						placeholder="Enter Your Email"
						bind:value={email}
						class="rounded-none border-0 border-b border-border bg-transparent px-0 shadow-none focus-visible:border-foreground focus-visible:ring-0"
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
							class="rounded-none border-0 border-b border-border bg-transparent px-0 pr-8 shadow-none focus-visible:border-foreground focus-visible:ring-0"
						/>
						<button
							type="button"
							class="absolute top-1/2 right-0 -translate-y-1/2 text-muted-foreground hover:text-foreground"
							onclick={() => (showPassword = !showPassword)}
						>
							{#if showPassword}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									width="18"
									height="18"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2"
									stroke-linecap="round"
									stroke-linejoin="round"
									><path
										d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
									/><line x1="1" y1="1" x2="23" y2="23" /></svg
								>
							{:else}
								<svg
									xmlns="http://www.w3.org/2000/svg"
									width="18"
									height="18"
									viewBox="0 0 24 24"
									fill="none"
									stroke="currentColor"
									stroke-width="2"
									stroke-linecap="round"
									stroke-linejoin="round"
									><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle
										cx="12"
										cy="12"
										r="3"
									/></svg
								>
							{/if}
						</button>
					</div>
				</div>

				<Button
					type="submit"
					class="w-full rounded-full bg-muted text-foreground shadow-none hover:bg-muted/80"
				>
					Create Account
				</Button>
			</form>

			<p class="text-center text-sm text-muted-foreground">
				Already have an account? <a
					href="/login"
					class="font-medium text-foreground underline underline-offset-4 hover:text-foreground/80"
					>Sign in</a
				>
			</p>
		</div>
	</div>
</div>
