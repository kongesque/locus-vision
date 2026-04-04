<script lang="ts">
	import { Button } from '$lib/components/ui/button/index.js';
	import { API_URL } from '$lib/api';
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import * as Tabs from '$lib/components/ui/tabs/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import { Label } from '$lib/components/ui/label/index.js';
	import { Plus, Loader2, RefreshCw, Camera, Globe } from '@lucide/svelte';
	import { goto } from '$app/navigation';
	import { videoStore } from '$lib/stores/video.svelte';

	import { untrack } from 'svelte';
	import { addCameraDialogOpen } from '$lib/stores/add-camera-dialog.svelte';

	let open = $state(false);

	// Subscribe to external dialog control
	addCameraDialogOpen.subscribe((value) => {
		if (value) {
			open = true;
			addCameraDialogOpen.set(false);
		}
	});

	let activeTab = $state('discovery');
	let isConnecting = $state(false);

	// Discovery state
	let isDiscovering = $state(false);
	interface DiscoveredCamera {
		name: string;
		type: 'v4l2' | 'onvif' | 'local';
		url: string;
		id: string;
	}
	let discoveredCameras = $state<DiscoveredCamera[]>([]);
	let selectedDiscoveryId = $state<string | null>(null);
	let previewUrl = $state<string | null>(null);

	async function runDiscovery() {
		try {
			isDiscovering = true;
			const response = await fetch(`${API_URL}/api/cameras/discover`);
			if (!response.ok) throw new Error('Discovery failed');
			discoveredCameras = await response.json();
		} catch (err) {
			console.error('Discovery error:', err);
		} finally {
			isDiscovering = false;
		}
	}

	function selectCamera(camId: string) {
		selectedDiscoveryId = camId;
		const cam = discoveredCameras.find((c) => c.id === camId);
		if (!cam) return;

		// Point directly at the MJPEG preview stream (browser renders it natively)
		previewUrl = `${API_URL}/api/cameras/preview?source=${encodeURIComponent(cam.url)}`;
	}

	// Manual RTSP/HTTP form fields
	let manualName = $state('');
	let manualUrl = $state('');
	let rtspPreview = $state<string | null>(null);
	let rtspPreviewError = $state<string | null>(null);
	let isTesting = $state(false);

	async function testConnection() {
		if (!manualUrl.trim()) return;
		try {
			isTesting = true;
			rtspPreviewError = null;
			rtspPreview = null;
			// Simulation for now
			await new Promise((resolve) => setTimeout(resolve, 1000));
			rtspPreview = '/locus.png';
		} catch (err) {
			rtspPreviewError = err instanceof Error ? err.message : 'Connection failed';
		} finally {
			isTesting = false;
		}
	}

	// Watch for dialog open to trigger discovery
	$effect(() => {
		if (open && activeTab === 'discovery') {
			untrack(() => {
				runDiscovery();
			});
		}
	});

	// Cleanup preview URL on dialog close
	$effect(() => {
		if (!open) {
			untrack(() => {
				previewUrl = null;
				selectedDiscoveryId = null;
			});
		}
	});

	async function handleConnect() {
		try {
			isConnecting = true;
			const cameraId = crypto.randomUUID();

			let config: {
				id: string;
				name: string;
				type: string;
				url: string | null;
				device_id: string | null;
			};

			if (activeTab === 'discovery' && selectedDiscoveryId) {
				const cam = discoveredCameras.find((c) => c.id === selectedDiscoveryId);
				if (!cam) return;
				const isLocal = cam.type === 'v4l2' || cam.type === 'local';
				config = {
					id: cameraId,
					name: cam.name,
					type: isLocal ? 'stream' : 'rtsp',
					url: !isLocal ? cam.url : null,
					device_id: isLocal ? cam.url : null
				};
			} else {
				config = {
					id: cameraId,
					name: manualName || 'Manual Stream',
					type: 'rtsp',
					url: manualUrl,
					device_id: null
				};
			}

			const response = await fetch(`${API_URL}/api/cameras`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(config)
			});

			if (!response.ok) {
				const errData = await response.json().catch(() => ({ detail: 'Unknown error' }));
				throw new Error(errData.detail || 'Failed to create camera');
			}

			// All camera types use 'rtsp' video type for the create page
			// since the backend serves all feeds via MJPEG at /api/livestream/{id}/video
			videoStore.setVideoType('rtsp');
			videoStore.setVideoUrl(config.url || config.device_id);

			open = false;
			goto(`/create/${cameraId}`);
		} catch (err) {
			console.error(err);
			alert('Failed to connect: ' + (err instanceof Error ? err.message : String(err)));
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
			<Dialog.Description>Connect via automatic discovery or manual configuration.</Dialog.Description>
		</Dialog.Header>

		<Tabs.Root bind:value={activeTab} class="w-full">
			<Tabs.List class="grid w-full grid-cols-2">
				<Tabs.Trigger value="discovery" class="cursor-pointer">Discovered</Tabs.Trigger>
				<Tabs.Trigger value="manual" class="cursor-pointer">Manual Entry</Tabs.Trigger>
			</Tabs.List>

			<Tabs.Content value="discovery" class="space-y-4 py-4">
				<div class="flex items-center justify-between">
					<Label>Available Devices</Label>
					<Button
						variant="ghost"
						size="sm"
						onclick={runDiscovery}
						disabled={isDiscovering}
						class="h-8 cursor-pointer"
					>
						<RefreshCw class="mr-2 size-3 {isDiscovering ? 'animate-spin' : ''}" />
						Refresh
					</Button>
				</div>

				<div class="max-h-[180px] space-y-2 overflow-y-auto rounded-md border p-2">
					{#if isDiscovering && discoveredCameras.length === 0}
						<div
							class="flex flex-col items-center justify-center py-8 text-center text-sm text-muted-foreground"
						>
							<Loader2 class="mb-2 size-6 animate-spin" />
							Scanning local network and hardware...
						</div>
					{:else if discoveredCameras.length === 0}
						<div class="py-8 text-center text-sm text-muted-foreground">
							No cameras found. Try manual entry or refresh.
						</div>
					{:else}
						{#each discoveredCameras as cam (cam.id)}
							<button
								class="flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors hover:bg-accent {selectedDiscoveryId ===
								cam.id
									? 'border-primary bg-primary/5'
									: ''}"
								onclick={() => selectCamera(cam.id)}
							>
								<div
									class="flex size-10 shrink-0 items-center justify-center rounded-full bg-muted"
								>
									{#if cam.type === 'v4l2' || cam.type === 'local'}
										<Camera class="size-5 text-muted-foreground" />
									{:else}
										<Globe class="size-5 text-muted-foreground" />
									{/if}
								</div>
								<div class="flex-1 overflow-hidden">
									<div class="truncate font-medium">{cam.name}</div>
									<div class="truncate text-xs text-muted-foreground">
										{cam.type.toUpperCase()} • {cam.url}
									</div>
								</div>
							</button>
						{/each}
					{/if}
				</div>

				<!-- Camera preview -->
				<div
					class="relative flex aspect-video items-center justify-center overflow-hidden rounded-md bg-black"
				>
					{#if previewUrl}
						<img src={previewUrl} alt="Camera preview" class="h-full w-full object-contain" />
					{:else}
						<div class="text-sm text-muted-foreground">
							Select a camera to preview
						</div>
					{/if}
				</div>
			</Tabs.Content>

			<Tabs.Content value="manual" class="space-y-4 py-4">
				<div class="space-y-2">
					<Label for="manual-name">Camera Name</Label>
					<Input
						id="manual-name"
						placeholder="e.g. Front Door"
						bind:value={manualName}
						disabled={isConnecting}
					/>
				</div>

				<div class="space-y-2">
					<Label for="manual-url">Stream URL</Label>
					<div class="flex gap-2">
						<Input
							id="manual-url"
							placeholder="rtsp://admin:password@192.168.1.10:554/stream"
							bind:value={manualUrl}
							disabled={isConnecting || isTesting}
							class="flex-1"
						/>
						<Button
							variant="outline"
							class="shrink-0 cursor-pointer"
							onclick={testConnection}
							disabled={!manualUrl.trim() || isTesting || isConnecting}
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
						<img src={rtspPreview} alt="Preview" class="h-full w-full object-cover" />
					{:else if isTesting}
						<div class="animate-pulse text-sm text-muted-foreground">Connecting...</div>
					{:else}
						<div class="text-sm text-muted-foreground">
							Enter a stream URL and click Test to preview
						</div>
					{/if}
				</div>
			</Tabs.Content>
		</Tabs.Root>

		<Dialog.Footer>
			<Button
				variant="outline"
				class="cursor-pointer"
				onclick={() => (open = false)}
				disabled={isConnecting}>Cancel</Button
			>
			<Button
				class="cursor-pointer"
				onclick={handleConnect}
				disabled={isConnecting ||
					(activeTab === 'manual' && (!manualName.trim() || !manualUrl.trim())) ||
					(activeTab === 'discovery' && !selectedDiscoveryId)}
			>
				{#if isConnecting}
					<Loader2 class="mr-2 size-4 animate-spin" />
					Connecting...
				{:else}
					Connect
				{/if}
			</Button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>
