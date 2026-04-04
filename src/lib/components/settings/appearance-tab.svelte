<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { setMode, resetMode } from 'mode-watcher';
</script>

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
