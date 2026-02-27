<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import * as Select from '$lib/components/ui/select/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Plus } from '@lucide/svelte';
	import { goto } from '$app/navigation';
	import { videoStore } from '$lib/stores/video.svelte';

	import { untrack } from 'svelte';

	let open = $state(false);
	let activeTab = $state('rtsp');
	let isConnecting = $state(false);

	// RTSP form fields
	let rtspName = $state('');
	let rtspUrl = $state('');
	let rtspPreview = $state<string | null>(null);
	let rtspPreviewError = $state<string | null>(null);
	let isTesting = $state(false);

	async function testRtspConnection() {
		if (!rtspUrl.trim()) return;
		try {
			isTesting = true;
			rtspPreviewError = null;
			rtspPreview = null;

			// TODO: Preview connection wire disconnected
			// The backend camera functionality has been deleted.
			//
			// Previous behavior:
			// const res = await fetch('http://localhost:8000/api/cameras/preview', { ... });

			throw new Error('Preview disconnected: see source code.');
			// const data = await res.json();
			// rtspPreview = data.image;
		} catch (err) {
			rtspPreviewError = err instanceof Error ? err.message : 'Connection failed';
		} finally {
			isTesting = false;
		}
	}

	// Webcam form fields
	let webcamName = $state('');
	let selectedDeviceId = $state<string | undefined>(undefined);

	let devices = $state<MediaDeviceInfo[]>([]);
	let localStream = $state<MediaStream | null>(null);
	let permissionError = $state<string | null>(null);
	let connectionSuccess = $state(false);

	async function startWebcam(deviceId?: string) {
		try {
			permissionError = null;
			if (localStream) {
				localStream.getTracks().forEach((t) => t.stop());
			}

			const constraints: MediaStreamConstraints = {
				video: deviceId && deviceId !== 'default' ? { deviceId: { exact: deviceId } } : true
			};

			const stream = await navigator.mediaDevices.getUserMedia(constraints);
			localStream = stream;

			// Get list of all video devices
			const allDevices = await navigator.mediaDevices.enumerateDevices();
			devices = allDevices.filter((d) => d.kind === 'videoinput');

			// Sync selected device with what the browser actually chose
			if (!deviceId && devices.length > 0 && stream.getVideoTracks().length > 0) {
				selectedDeviceId = stream.getVideoTracks()[0].getSettings().deviceId;
			}
		} catch (err) {
			console.error('Webcam error:', err);
			permissionError = 'Could not access camera. Please check permissions.';
		}
	}

	function stopWebcam() {
		if (localStream) {
			localStream.getTracks().forEach((t) => t.stop());
			localStream = null;
		}
	}

	// Watch for dialog open/close and tab changes
	$effect(() => {
		const isOpen = open;
		const tab = activeTab;

		untrack(() => {
			if (isOpen && tab === 'webcam') {
				if (!localStream) {
					startWebcam(selectedDeviceId);
				}
			} else if (!isOpen && !connectionSuccess) {
				stopWebcam();
			}
		});
	});

	// Watch for manual device changes from the dropdown
	$effect(() => {
		const deviceId = selectedDeviceId;
		untrack(() => {
			if (open && activeTab === 'webcam' && localStream) {
				const currentDeviceId = localStream.getVideoTracks()[0]?.getSettings().deviceId;
				if (deviceId && deviceId !== 'default' && deviceId !== currentDeviceId) {
					startWebcam(deviceId);
				}
			}
		});
	});

	// Svelte action to pipe the MediaStream into the video element
	function videoAction(node: HTMLVideoElement, stream: MediaStream | null) {
		if (stream) {
			node.srcObject = stream;
		}
		return {
			update(newStream: MediaStream | null) {
				if (node.srcObject !== newStream) {
					node.srcObject = newStream;
				}
			}
		};
	}

	async function handleConnect() {
		try {
			isConnecting = true;
			const cameraId = crypto.randomUUID();
			const config = {
				id: cameraId,
				name: activeTab === 'webcam' ? webcamName || 'Webcam' : rtspName || 'RTSP Stream',
				type: activeTab,
				url: activeTab === 'rtsp' ? rtspUrl : null,
				device_id: activeTab === 'webcam' ? selectedDeviceId : null
			};

			// TODO: Camera creation wire disconnected
			// The backend camera functionality has been deleted.
			//
			// Previous behavior:
			// const response = await fetch('http://localhost:8000/api/cameras/', { ... });

			throw new Error('Creation disconnected: see source code.');

			videoStore.setVideoType(activeTab as 'rtsp' | 'stream');
			if (activeTab === 'rtsp') {
				videoStore.setVideoUrl(rtspUrl);
			} else {
				videoStore.setVideoType('stream');
				// Save active stream so it plays on the next page
				videoStore.setVideoStream(localStream);
				connectionSuccess = true; // prevent the stream from closing when dialog hides
			}

			open = false;
			goto(`/create/${cameraId}`);
		} catch (err) {
			console.error(err);
			alert('Failed to connect camera: ' + (err instanceof Error ? err.message : String(err)));
		} finally {
			isConnecting = false;
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
					<Input
						id="rtsp-name"
						placeholder="e.g. Front Door"
						bind:value={rtspName}
						disabled={isConnecting}
					/>
				</div>
				<div class="space-y-2">
					<Label for="rtsp-url">Stream URL</Label>
					<div class="flex gap-2">
						<Input
							id="rtsp-url"
							placeholder="rtsp://admin:password@192.168.1.10:554/stream"
							bind:value={rtspUrl}
							disabled={isConnecting || isTesting}
							class="flex-1"
						/>
						<Button
							variant="outline"
							class="shrink-0 cursor-pointer"
							onclick={testRtspConnection}
							disabled={!rtspUrl.trim() || isTesting || isConnecting}
						>
							{isTesting ? 'Testing...' : 'Test'}
						</Button>
					</div>
				</div>

				<div
					class="relative flex aspect-video items-center justify-center overflow-hidden rounded-md bg-black"
				>
					{#if rtspPreviewError}
						<div class="px-4 text-center text-sm text-red-500">{rtspPreviewError}</div>
					{:else if rtspPreview}
						<img src={rtspPreview} alt="RTSP Preview" class="h-full w-full object-cover" />
					{:else if isTesting}
						<div class="animate-pulse text-sm text-muted-foreground">Connecting to stream...</div>
					{:else}
						<div class="text-sm text-muted-foreground">
							Enter a stream URL and click Test to preview
						</div>
					{/if}
				</div>
			</Tabs.Content>

			<Tabs.Content value="webcam" class="space-y-4 py-4">
				<div class="space-y-2">
					<Label for="webcam-name">Camera Name</Label>
					<Input
						id="webcam-name"
						placeholder="e.g. Desk Webcam"
						bind:value={webcamName}
						disabled={isConnecting}
					/>
				</div>
				<div class="space-y-2">
					<Label for="device">Device</Label>
					<Select.Root type="single" bind:value={selectedDeviceId} disabled={isConnecting}>
						<Select.Trigger id="device" placeholder="Select a device" />
						<Select.Content>
							{#each devices as device (device.deviceId)}
								<Select.Item value={device.deviceId}
									>{device.label || `Camera ${devices.indexOf(device) + 1}`}</Select.Item
								>
							{/each}
						</Select.Content>
					</Select.Root>
				</div>

				<div
					class="relative flex aspect-video items-center justify-center overflow-hidden rounded-md bg-black"
				>
					{#if permissionError}
						<div class="px-4 text-center text-sm text-red-500">{permissionError}</div>
					{:else if localStream}
						<video
							use:videoAction={localStream}
							autoplay
							playsinline
							muted
							class="h-full w-full object-cover"
						></video>
					{:else}
						<div class="animate-pulse text-sm text-muted-foreground">
							Requesting camera access...
						</div>
					{/if}
				</div>
			</Tabs.Content>
		</Tabs.Root>

		<Dialog.Footer>
			<Button
				variant="outline"
				class="cursor-pointer"
				onclick={() => {
					open = false;
					stopWebcam();
				}}
				disabled={isConnecting}>Cancel</Button
			>
			<Button class="cursor-pointer" onclick={handleConnect} disabled={isConnecting}>
				{isConnecting ? 'Connecting...' : 'Connect'}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
