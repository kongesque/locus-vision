<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import * as Select from '$lib/components/ui/select/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Plus } from '@lucide/svelte';

	let open = $state(false);
	let activeTab = $state('rtsp');

	// RTSP form fields
	let rtspName = $state('');
	let rtspUrl = $state('');

	// Webcam form fields
	let webcamName = $state('');
	let selectedDeviceId = $state<string | undefined>(undefined);

	function handleConnect() {
		open = false;

		if (activeTab === 'webcam') {
			// TODO: Handle webcam connection
			// - Request camera access via navigator.mediaDevices.getUserMedia()
			// - Save camera configuration via POST /api/cameras
			console.log('Connect webcam:', { name: webcamName, deviceId: selectedDeviceId });
		} else {
			// TODO: Handle RTSP connection
			// - Validate RTSP URL format
			// - Test connection to RTSP stream
			// - Save camera configuration via POST /api/cameras
			console.log('Connect RTSP:', { name: rtspName, url: rtspUrl });
		}
	}
</script>

<Dialog.Root bind:open>
	<Dialog.Trigger>
		{#snippet child({ props })}
			<Button {...props} variant="default" class="cursor-pointer">
				<Plus class="size-4" />
				Add Camera
			</Button>
		{/snippet}
	</Dialog.Trigger>

	<Dialog.Content class="sm:max-w-[500px]">
		<Dialog.Header>
			<Dialog.Title>Add Camera</Dialog.Title>
			<Dialog.Description>Connect a new camera via RTSP stream or local webcam.</Dialog.Description>
		</Dialog.Header>

		<Tabs.Root bind:value={activeTab} class="w-full">
			<Tabs.List class="grid w-full grid-cols-2">
				<Tabs.Trigger value="rtsp" class="cursor-pointer">RTSP / HTTP</Tabs.Trigger>
				<Tabs.Trigger value="webcam" class="cursor-pointer">Webcam</Tabs.Trigger>
			</Tabs.List>

			<Tabs.Content value="rtsp" class="space-y-4 py-4">
				<div class="space-y-2">
					<Label for="rtsp-name">Camera Name</Label>
					<Input id="rtsp-name" placeholder="e.g. Front Door" bind:value={rtspName} />
				</div>
				<div class="space-y-2">
					<Label for="rtsp-url">Stream URL</Label>
					<Input
						id="rtsp-url"
						placeholder="rtsp://admin:password@192.168.1.10:554/stream"
						bind:value={rtspUrl}
					/>
				</div>
			</Tabs.Content>

			<Tabs.Content value="webcam" class="space-y-4 py-4">
				<div class="space-y-2">
					<Label for="webcam-name">Camera Name</Label>
					<Input id="webcam-name" placeholder="e.g. Desk Webcam" bind:value={webcamName} />
				</div>
				<div class="space-y-2">
					<Label for="device">Device</Label>
					<Select.Root type="single" bind:value={selectedDeviceId}>
						<Select.Trigger id="device" placeholder="Select a device" />
						<Select.Content>
							<Select.Item value="default">Default Camera</Select.Item>
							<!-- TODO: Populate with real devices from navigator.mediaDevices.enumerateDevices() -->
						</Select.Content>
					</Select.Root>
				</div>

				<div
					class="relative flex aspect-video items-center justify-center overflow-hidden rounded-md bg-black"
				>
					<!-- TODO: Implement webcam preview -->
					<!-- - Request camera access when webcam tab is active -->
					<!-- - Display live video feed in this area -->
					<!-- - Handle permission errors gracefully -->
					<div class="text-sm text-muted-foreground">Camera preview will appear here</div>
				</div>
			</Tabs.Content>
		</Tabs.Root>

		<Dialog.Footer>
			<Button variant="outline" class="cursor-pointer" onclick={() => (open = false)}>Cancel</Button
			>
			<!-- TODO: Implement backend integration -->
			<!-- - POST /api/cameras to save new camera configuration -->
			<!-- - Handle connection testing before saving -->
			<Button class="cursor-pointer" onclick={handleConnect}>Connect</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
