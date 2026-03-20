<script lang="ts">
	import * as Card from '$lib/components/ui/card';
	import { Separator } from '$lib/components/ui/separator';
	import { Button, buttonVariants } from '$lib/components/ui/button';
	import * as Tooltip from '$lib/components/ui/tooltip';
	import * as Select from '$lib/components/ui/select';
	import * as Tabs from '$lib/components/ui/tabs';
	import * as ToggleGroup from '$lib/components/ui/toggle-group';
	import * as Command from '$lib/components/ui/command';
	import * as Popover from '$lib/components/ui/popover';
	import { Input } from '$lib/components/ui/input';
	import { Slider } from '$lib/components/ui/slider';

	// Icons
	import {
		Slash,
		Square,
		X,
		Info,
		Check,
		ChevronsUpDown,
		ArrowUpDown,
		ArrowDown,
		ArrowUp
	} from '@lucide/svelte';

	import { cn } from '$lib/utils';
	import type { Zone } from './drawing-canvas.svelte';
	import { COCO_CLASSES } from '$lib/coco-classes';
	import { tick } from 'svelte';

	interface ModelInfo {
		value: string;
		label: string;
		desc: string;
		size: string;
	}

	interface Props {
		zones: Zone[];
		selectedZoneId: string | null;
		drawingMode: 'polygon' | 'line';
		fullFrameClasses: string[];
		selectedModel: string;
		selectedPrecision: 'fp32' | 'fp16' | 'int8';
		allModels: ModelInfo[];
		downloadedModels: string[];
		isModelMissing: boolean;
		isDownloadingModel: boolean;
		modelDownloadStatus: { status: string; error?: string } | null;
		onDrawingModeChange: (mode: 'polygon' | 'line') => void;
		onZoneSelected: (id: string | null) => void;
		onDeleteZone: (id: string, e: MouseEvent) => void;
		onProcess: (mode: 'zone-based' | 'full-frame') => void;
		onDownloadModel: () => void;
		onZoneRenamed: (id: string, name: string) => void;
		onZoneClassesChanged: (id: string, classes: string[]) => void;
		onZoneDirectionChanged: (id: string, direction: 'both' | 'in' | 'out') => void;
		onFullFrameClassesChanged: (classes: string[]) => void;
		onModelChange: (model: string) => void;
		onPrecisionChange: (precision: 'fp32' | 'fp16' | 'int8') => void;
		fps: number;
		onFpsChange: (fps: number) => void;
		confidenceThreshold: number;
		onConfidenceThresholdChange: (value: number) => void;
	}

	let {
		zones,
		selectedZoneId,
		drawingMode,
		fullFrameClasses,
		selectedModel,
		selectedPrecision,
		allModels = [],
		downloadedModels = [],
		isModelMissing = false,
		isDownloadingModel = false,
		modelDownloadStatus = null,
		onDrawingModeChange,
		onZoneSelected,
		onDeleteZone,
		onProcess,
		onDownloadModel,
		onZoneRenamed,
		onZoneClassesChanged,
		onZoneDirectionChanged,
		onFullFrameClassesChanged,
		onModelChange,
		onPrecisionChange,
		fps,
		onFpsChange,
		confidenceThreshold,
		onConfidenceThresholdChange
	}: Props = $props();

	// Helper: find model info for the currently selected model
	const selectedModelInfo = $derived(allModels.find((m) => m.value === selectedModel));

	let editingId = $state<string | null>(null);
	let tempName = $state('');

	// Combobox states
	let openZoneCombobox = $state<string | null>(null); // zone id
	let openFullFrameCombobox = $state(false);

	let activeTab = $state<'zone-based' | 'full-frame'>('zone-based');
	let scrollContainer: HTMLDivElement | undefined = $state();
	let prevZoneCount = $state(0);

	$effect(() => {
		if (zones.length > prevZoneCount && scrollContainer) {
			tick().then(() => {
				scrollContainer?.scrollTo({ top: scrollContainer.scrollHeight, behavior: 'smooth' });
			});
			prevZoneCount = zones.length;
		}
	});

	function handleStartEditing(id: string, currentName: string) {
		editingId = id;
		tempName = currentName;
	}

	function handleFinishEditing() {
		if (editingId && tempName.trim()) {
			onZoneRenamed(editingId, tempName.trim());
		}
		editingId = null;
		tempName = '';
	}

	function handleKeyDown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			handleFinishEditing();
		} else if (e.key === 'Escape') {
			editingId = null;
			tempName = '';
		}
	}

	// Helper for class toggle
	function toggleClass(currentClasses: string[], className: string) {
		if (currentClasses.includes(className)) {
			return currentClasses.filter((c) => c !== className);
		} else {
			return [...currentClasses, className];
		}
	}

	// Helper for checking if precision is downloaded for the selected model
	function isPrecisionDownloaded(p: string) {
		let checkName = selectedModel;
		if (p === 'int8') checkName += '_int8';
		if (p === 'fp16') checkName += '_half';
		return downloadedModels.includes(checkName);
	}
</script>

<Card.Root class="flex flex-col overflow-hidden">
	<div bind:this={scrollContainer} class="flex-1 min-h-0 overflow-y-auto p-3">
		<div class="space-y-3">
			<h3 class="text-sm font-semibold">Create</h3>
			<Separator />

			<!-- Model Selection -->
			<div>
				<div class="mb-1.5 flex items-center justify-between">
					<div class="text-sm font-semibold text-foreground">Model</div>
					<Tooltip.Root>
						<Tooltip.Trigger class={buttonVariants({ variant: 'ghost', size: 'icon' })}>
							<Info class="h-4 w-4" />
							<span class="sr-only">Info</span>
						</Tooltip.Trigger>
						<Tooltip.Content side="left">
							<p>Smaller = faster</p>
							<p>larger = more accurate</p>
						</Tooltip.Content>
					</Tooltip.Root>
				</div>

				<Select.Root
					type="single"
					bind:value={selectedModel}
					onValueChange={(v) => {
						if (v) onModelChange(v);
					}}
				>
					<Select.Trigger class="h-auto w-full">
						<div class="flex items-center gap-2">
							<span class="font-medium">{selectedModelInfo?.label || selectedModel}</span>
							<span class="text-xs text-muted-foreground">· {selectedModelInfo?.desc || ''}</span>
						</div>
					</Select.Trigger>
					<Select.Content>
						{#each allModels as model}
							<Select.Item value={model.value} label={model.label}>
								<div class="flex w-full items-center justify-between gap-3">
									<div class="flex flex-col">
										<span class="font-medium">{model.label}</span>
										<span class="text-[11px] text-muted-foreground">{model.desc} · {model.size}</span>
									</div>
									{#if !downloadedModels.some((d) => d.startsWith(model.value))}
										<span
											class="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
											>not downloaded</span
										>
									{/if}
								</div>
							</Select.Item>
						{/each}
					</Select.Content>
				</Select.Root>

				<!-- Inference Precision -->
				<div class="mt-2">
					<span class="mb-1 block text-xs font-medium text-muted-foreground"
						>Inference Precision</span
					>
					<ToggleGroup.Root
						type="single"
						value={selectedPrecision}
						onValueChange={(v) => v && onPrecisionChange(v as 'fp32' | 'fp16' | 'int8')}
						class="w-full justify-stretch gap-1"
					>
						<ToggleGroup.Item value="int8" aria-label="INT8" class="flex-1 gap-1 text-xs">
							INT8
							{#if isPrecisionDownloaded('int8')}
								<span
									class="rounded-full bg-green-500/20 px-1.5 py-0.5 text-[9px] font-medium text-green-600 dark:text-green-400"
									>ready</span
								>
							{:else}
								<span
									class="rounded-full border bg-muted/50 px-1.5 py-0.5 text-[9px] text-muted-foreground"
									>missing</span
								>
							{/if}
						</ToggleGroup.Item>
						<ToggleGroup.Item value="fp16" aria-label="FP16" class="flex-1 gap-1 text-xs">
							FP16
							{#if isPrecisionDownloaded('fp16')}
								<span
									class="rounded-full bg-green-500/20 px-1.5 py-0.5 text-[9px] font-medium text-green-600 dark:text-green-400"
									>ready</span
								>
							{:else}
								<span
									class="rounded-full border bg-muted/50 px-1.5 py-0.5 text-[9px] text-muted-foreground"
									>missing</span
								>
							{/if}
						</ToggleGroup.Item>
						<ToggleGroup.Item value="fp32" aria-label="FP32" class="flex-1 gap-1 text-xs">
							FP32
							{#if isPrecisionDownloaded('fp32')}
								<span
									class="rounded-full bg-green-500/20 px-1.5 py-0.5 text-[9px] font-medium text-green-600 dark:text-green-400"
									>ready</span
								>
							{:else}
								<span
									class="rounded-full border bg-muted/50 px-1.5 py-0.5 text-[9px] text-muted-foreground"
									>missing</span
								>
							{/if}
						</ToggleGroup.Item>
					</ToggleGroup.Root>
				</div>

				<!-- Download Status UI -->
				{#if isModelMissing}
					<div class="mt-2.5 rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5">
						<div class="flex flex-col gap-2">
							<div class="text-xs font-medium text-amber-600 dark:text-amber-500">
								Model not downloaded
							</div>
							<div class="text-[11px] text-muted-foreground">
								This combination needs to be downloaded before processing.
							</div>
							{#if isDownloadingModel}
								<div class="mt-1 flex items-center justify-between">
									<div class="flex items-center gap-2">
										<div
											class="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent"
										></div>
										<span class="text-xs font-medium capitalize">
											{modelDownloadStatus?.status || 'Starting...'}
										</span>
									</div>
								</div>
							{:else if modelDownloadStatus?.status === 'error'}
								<div class="mt-1 text-xs text-red-500">
									Error: {modelDownloadStatus.error}
								</div>
								<Button
									size="sm"
									variant="outline"
									class="mt-2 w-full text-xs"
									onclick={onDownloadModel}
								>
									Retry Download
								</Button>
							{:else}
								<Button
									size="sm"
									variant="outline"
									class="mt-1 w-full text-xs"
									onclick={onDownloadModel}
								>
									Auto-Download Now
								</Button>
							{/if}
						</div>
					</div>
				{/if}
			</div>

			<!-- FPS -->
			<div>
				<div class="mb-1.5 flex items-center justify-between">
					<div class="text-sm font-semibold text-foreground">FPS</div>
					<Tooltip.Root>
						<Tooltip.Trigger class={buttonVariants({ variant: 'ghost', size: 'icon' })}>
							<Info class="h-4 w-4" />
							<span class="sr-only">Info</span>
						</Tooltip.Trigger>
						<Tooltip.Content side="left">
							<p>Higher = smoother but heavier.</p>
							<p>Lower = lighter but choppy.</p>
						</Tooltip.Content>
					</Tooltip.Root>
				</div>
				<div class="flex items-center gap-3">
					<Slider
						type="single"
						value={fps}
						min={5}
						max={30}
						step={1}
						onValueChange={(v: number) => onFpsChange(v)}
						class="flex-1"
					/>
					<Input
						type="number"
						min={5}
						max={30}
						value={fps}
						oninput={(e) => {
							const val = parseInt(e.currentTarget.value);
							if (!isNaN(val) && val >= 5 && val <= 30) {
								onFpsChange(val);
							}
						}}
						onblur={(e) => {
							// Snap back to current fps if empty or invalid on blur
							e.currentTarget.value = String(fps);
						}}
						class="h-7 w-14 px-1.5 text-center font-mono text-xs"
					/>
				</div>
			</div>

			<!-- Confidence Threshold -->
			<div>
				<div class="mb-1.5 flex items-center justify-between">
					<div class="text-sm font-semibold text-foreground">Confidence</div>
					<Tooltip.Root>
						<Tooltip.Trigger class={buttonVariants({ variant: 'ghost', size: 'icon' })}>
							<Info class="h-4 w-4" />
							<span class="sr-only">Info</span>
						</Tooltip.Trigger>
						<Tooltip.Content side="left">
							<p>Higher = fewer, more confident detections.</p>
							<p>Lower = more detections, more noise.</p>
						</Tooltip.Content>
					</Tooltip.Root>
				</div>
				<div class="flex items-center gap-3">
					<Slider
						type="single"
						value={confidenceThreshold}
						min={0.05}
						max={0.95}
						step={0.05}
						onValueChange={(v: number) => onConfidenceThresholdChange(v)}
						class="flex-1"
					/>
					<Input
						type="number"
						min={0.05}
						max={0.95}
						step={0.05}
						value={confidenceThreshold}
						oninput={(e) => {
							const val = parseFloat(e.currentTarget.value);
							if (!isNaN(val) && val >= 0.05 && val <= 0.95) {
								onConfidenceThresholdChange(Math.round(val * 100) / 100);
							}
						}}
						onblur={(e) => {
							e.currentTarget.value = String(confidenceThreshold);
						}}
						class="h-7 w-14 px-1.5 text-center font-mono text-xs"
					/>
				</div>
			</div>

			<Separator />

			<!-- Tools & Zones -->
			<div>
				<div class="mb-1.5 flex items-center justify-between">
					<div class="text-sm font-semibold text-foreground">Tools</div>
					<Tooltip.Root>
						<Tooltip.Trigger class={buttonVariants({ variant: 'ghost', size: 'icon' })}>
							<Info class="h-4 w-4" />
							<span class="sr-only">Info</span>
						</Tooltip.Trigger>
						<Tooltip.Content side="left">
							<p>Zone = detect in specific areas.</p>
							<p>Full frame = detect everywhere.</p>
						</Tooltip.Content>
					</Tooltip.Root>
				</div>

				<Tabs.Root bind:value={activeTab} class="w-full">
					<Tabs.List class="w-full">
						<Tabs.Trigger value="zone-based" class="flex-1">Zone based</Tabs.Trigger>
						<Tabs.Trigger value="full-frame" class="flex-1">Full frame</Tabs.Trigger>
					</Tabs.List>

					<div class="mt-2 rounded-xl border border-border p-1.5">
						<Tabs.Content value="zone-based">
							<div class="flex min-h-0 flex-1 flex-col gap-2">
								<ToggleGroup.Root
									type="single"
									value={drawingMode}
									onValueChange={(v) => v && onDrawingModeChange(v as 'polygon' | 'line')}
									class="w-full justify-stretch"
								>
									<ToggleGroup.Item value="polygon" aria-label="Zone" class="flex-1 gap-2">
										<Square class="h-4 w-4" />
										Zone
									</ToggleGroup.Item>
									<ToggleGroup.Item value="line" aria-label="Line" class="flex-1 gap-2">
										<Slash class="h-4 w-4" />
										Line
									</ToggleGroup.Item>
								</ToggleGroup.Root>

								<div class="flex max-h-[400px] min-h-0 flex-1 flex-col">
									<div class="-mx-2 flex-1 overflow-y-auto px-2">
										<div class="flex flex-col gap-2">
											{#if zones.length === 0}
												<div
													class="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground"
												>
													Click on the video to create a zone
												</div>
											{:else}
												{#each zones as zone, index (zone.id)}
													<!-- Zone Item -->
													<div
														class={cn(
															'group flex flex-col rounded-lg border transition-all duration-150',
															selectedZoneId === zone.id
																? 'border-yellow-500/50 bg-muted'
																: 'border-border bg-muted hover:border-yellow-500/50'
														)}
													>
														<!-- Header Row -->
														<!-- svelte-ignore a11y_click_events_have_key_events -->
														<!-- svelte-ignore a11y_no_static_element_interactions -->
														<div
															class="flex cursor-pointer items-center gap-2.5 px-2.5 py-2"
															onclick={() => onZoneSelected(zone.id)}
														>
															<div
																class={cn(
																	'h-2.5 w-2.5 shrink-0 rounded-full transition-colors',
																	selectedZoneId === zone.id
																		? 'bg-yellow-500'
																		: 'bg-muted-foreground/40'
																)}
															></div>

															<div class="min-w-0 flex-1">
																{#if editingId === zone.id}
																	<Input
																		class="h-6 text-sm"
																		bind:value={tempName}
																		onblur={handleFinishEditing}
																		autofocus
																		onclick={(e) => e.stopPropagation()}
																		onkeydown={handleKeyDown}
																	/>
																{:else}
																	<span
																		class="block truncate text-sm font-medium"
																		ondblclick={(e) => {
																			e.stopPropagation();
																			handleStartEditing(zone.id, zone.name);
																		}}
																	>
																		{zone.name || `Zone ${index + 1}`}
																	</span>
																{/if}
															</div>

															<span
																class={cn(
																	'shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px]',
																	'bg-yellow-500/20 text-yellow-600 dark:text-yellow-400'
																)}
															>
																{zone.classes.length === 0 ? 'ALL' : zone.classes.length}
															</span>

															<Button
																variant="ghost"
																size="icon"
																class="h-6 w-6 cursor-pointer hover:text-destructive"
																onclick={(e) => {
																	e.stopPropagation();
																	onDeleteZone(zone.id, e);
																}}
															>
																<X class="h-3 w-3" />
															</Button>
														</div>

														<!-- Expanded Content -->
														{#if selectedZoneId === zone.id}
															<div
																class="px-2.5 pt-0 pb-2.5"
																onclick={(e) => e.stopPropagation()}
																role="presentation"
															>
																<Popover.Root
																	bind:open={
																		() => openZoneCombobox === zone.id,
																		(v) => (openZoneCombobox = v ? zone.id : null)
																	}
																>
																	<Popover.Trigger
																		role="combobox"
																		aria-expanded={openZoneCombobox === zone.id}
																		class={cn(
																			buttonVariants({ variant: 'outline' }),
																			'h-auto min-h-[32px] w-full justify-between px-2 py-1 text-xs'
																		)}
																	>
																		<div class="flex flex-wrap gap-1">
																			{#if zone.classes.length === 0}
																				Filter classes...
																			{:else}
																				{#each zone.classes as cls}
																					<span
																						class="rounded bg-secondary px-1 font-mono text-[10px] text-secondary-foreground"
																						>{cls}</span
																					>
																				{/each}
																			{/if}
																		</div>
																		<ChevronsUpDown class="ml-2 h-3 w-3 shrink-0 opacity-50" />
																	</Popover.Trigger>
																	<Popover.Content class="w-[200px] p-0">
																		<Command.Root>
																			<Command.Input
																				placeholder="Search classes..."
																				class="h-8 text-xs"
																			/>
																			<Command.Empty>No class found.</Command.Empty>
																			<Command.Group class="max-h-[200px] overflow-auto">
																				{#each COCO_CLASSES as cls}
																					<Command.Item
																						value={cls}
																						onSelect={() => {
																							onZoneClassesChanged(
																								zone.id,
																								toggleClass(zone.classes, cls)
																							);
																						}}
																						class="text-xs"
																					>
																						<Check
																							class={cn(
																								'mr-2 h-3 w-3',
																								zone.classes.includes(cls) ? 'opacity-100' : 'opacity-0'
																							)}
																						/>
																						{cls}
																					</Command.Item>
																				{/each}
																			</Command.Group>
																		</Command.Root>
																	</Popover.Content>
																</Popover.Root>

																{#if zone.type === 'line'}
																	<div class="mt-2">
																		<span
																			class="mb-1 block text-[11px] font-medium text-muted-foreground"
																			>Crossing Direction</span
																		>
																		<ToggleGroup.Root
																			type="single"
																			value={zone.direction || 'both'}
																			onValueChange={(v) =>
																				v &&
																				onZoneDirectionChanged(zone.id, v as 'both' | 'in' | 'out')}
																			class="w-full justify-stretch gap-1 rounded-md bg-muted p-1"
																		>
																			<ToggleGroup.Item
																				value="both"
																				aria-label="A ↔ B"
																				class="flex-1 gap-1 rounded-[4px] font-mono text-[10px] data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
																			>
																				<ArrowUpDown class="h-3 w-3" />
																				A ↔ B
																			</ToggleGroup.Item>
																			<ToggleGroup.Item
																				value="in"
																				aria-label="A → B"
																				class="flex-1 gap-1 rounded-[4px] font-mono text-[10px] data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
																			>
																				<ArrowDown class="h-3 w-3" />
																				A → B
																			</ToggleGroup.Item>
																			<ToggleGroup.Item
																				value="out"
																				aria-label="B → A"
																				class="flex-1 gap-1 rounded-[4px] font-mono text-[10px] data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
																			>
																				<ArrowUp class="h-3 w-3" />
																				B → A
																			</ToggleGroup.Item>
																		</ToggleGroup.Root>
																	</div>
																{/if}
															</div>
														{/if}
													</div>
												{/each}
											{/if}
										</div>
									</div>
								</div>
							</div>
						</Tabs.Content>

						<Tabs.Content value="full-frame">
							<div class="group flex flex-col rounded-lg border border-border bg-muted">
								<div class="">
									<div class="flex items-center justify-between gap-2.5 px-2.5 py-2">
										<span class="text-sm font-medium text-muted-foreground">Detect classes</span>
										<span
											class={cn(
												'rounded px-1.5 py-0.5 font-mono text-[10px]',
												'bg-yellow-500/20 text-yellow-600 dark:text-yellow-400'
											)}
										>
											{fullFrameClasses.length === 0 ? 'ALL' : fullFrameClasses.length}
										</span>
									</div>
									<div class="px-2.5 pt-0 pb-2.5">
										<Popover.Root bind:open={openFullFrameCombobox}>
											<Popover.Trigger
												role="combobox"
												aria-expanded={openFullFrameCombobox}
												class={cn(
													buttonVariants({ variant: 'outline' }),
													'h-auto min-h-[32px] w-full justify-between px-2 py-1 text-xs'
												)}
											>
												<div class="flex flex-wrap gap-1">
													{#if fullFrameClasses.length === 0}
														Filter classes...
													{:else}
														{#each fullFrameClasses as cls}
															<span
																class="rounded bg-secondary px-1 font-mono text-[10px] text-secondary-foreground"
																>{cls}</span
															>
														{/each}
													{/if}
												</div>
												<ChevronsUpDown class="ml-2 h-3 w-3 shrink-0 opacity-50" />
											</Popover.Trigger>
											<Popover.Content class="w-[200px] p-0">
												<Command.Root>
													<Command.Input placeholder="Search classes..." class="h-8 text-xs" />
													<Command.Empty>No class found.</Command.Empty>
													<Command.Group class="max-h-[200px] overflow-auto">
														{#each COCO_CLASSES as cls}
															<Command.Item
																value={cls}
																onSelect={() => {
																	onFullFrameClassesChanged(toggleClass(fullFrameClasses, cls));
																}}
																class="text-xs"
															>
																<Check
																	class={cn(
																		'mr-2 h-3 w-3',
																		fullFrameClasses.includes(cls) ? 'opacity-100' : 'opacity-0'
																	)}
																/>
																{cls}
															</Command.Item>
														{/each}
													</Command.Group>
												</Command.Root>
											</Popover.Content>
										</Popover.Root>
									</div>
								</div>
							</div>
						</Tabs.Content>
					</div>
				</Tabs.Root>
			</div>
		</div>
	</div>

	<div class="border-t p-3">
		<Separator class="my-2.5" />
		<Button
			class="h-10 w-full text-sm"
			disabled={(activeTab === 'zone-based' && zones.length === 0) ||
				isModelMissing ||
				isDownloadingModel}
			onclick={() => onProcess(activeTab)}
		>
			Process
		</Button>
	</div>
</Card.Root>
