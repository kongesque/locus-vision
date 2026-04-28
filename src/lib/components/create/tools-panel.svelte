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
	import { hexToRgba } from '$lib/zone-colors';
	import { tick } from 'svelte';

	interface InstalledModel {
		name: string;
		label: string;
		fps_estimate?: number | null;
		active_format?: string | null;
	}

	interface Props {
		zones: Zone[];
		selectedZoneId: string | null;
		drawingMode: 'polygon' | 'line';
		fullFrameClasses: string[];
		selectedModel: string;
		installedModels: InstalledModel[];
		onDrawingModeChange: (mode: 'polygon' | 'line') => void;
		onZoneSelected: (id: string | null) => void;
		onDeleteZone: (id: string, e: MouseEvent) => void;
		onProcess: (mode: 'zone-based' | 'full-frame') => void;
		onZoneRenamed: (id: string, name: string) => void;
		onZoneClassesChanged: (id: string, classes: string[]) => void;
		onZoneDirectionChanged: (id: string, direction: 'both' | 'in' | 'out') => void;
		onFullFrameClassesChanged: (classes: string[]) => void;
		onModelChange: (model: string) => void;
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
		installedModels = [],
		onDrawingModeChange,
		onZoneSelected,
		onDeleteZone,
		onProcess,
		onZoneRenamed,
		onZoneClassesChanged,
		onZoneDirectionChanged,
		onFullFrameClassesChanged,
		onModelChange,
		fps,
		onFpsChange,
		confidenceThreshold,
		onConfidenceThresholdChange
	}: Props = $props();

	// Helper: find model info for the currently selected model
	const selectedModelInfo = $derived(installedModels.find((m) => m.name === selectedModel));

	let editingId = $state<string | null>(null);
	let tempName = $state('');

	// Combobox states
	let openZoneCombobox = $state<string | null>(null); // zone id
	let openFullFrameCombobox = $state(false);

	let activeTab = $state<'zone-based' | 'full-frame'>('zone-based');
	let scrollContainer: HTMLDivElement | undefined = $state();
	let prevZoneCount = $state(0);

	// Format backend names for display
	function formatBackend(fmt: string | null | undefined): string {
		if (!fmt) return '';
		const map: Record<string, string> = {
			hailo: 'Hailo',
			onnx_int8: 'INT8',
			onnx_fp16: 'FP16',
			onnx_fp32: 'FP32',
			onnx_cuda: 'CUDA',
			onnx_coreml: 'CoreML'
		};
		return map[fmt] ?? fmt;
	}

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
</script>

<Card.Root class="flex h-full flex-col gap-0 overflow-hidden py-0">
	<div bind:this={scrollContainer} class="min-h-0 flex-1 overflow-y-auto p-3">
		<div class="space-y-3">
			<h3 class="text-md font-semibold">Create</h3>
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
							<p>Smaller models run faster but are less accurate</p>
							<p>Manage models in Settings → Models</p>
						</Tooltip.Content>
					</Tooltip.Root>
				</div>

				{#if installedModels.length === 0}
					<div class="rounded-md border border-amber-500/30 bg-amber-500/10 p-2.5">
						<div class="text-xs font-medium text-amber-600 dark:text-amber-500">
							No models installed
						</div>
						<div class="mt-1 text-[11px] text-muted-foreground">
							Download a model to get started.
						</div>
						<a href="/settings" class="mt-2 inline-block cursor-pointer text-xs font-medium text-primary hover:underline">
							Go to Settings → Models
						</a>
					</div>
				{:else}
					<Select.Root
						type="single"
						bind:value={selectedModel}
						onValueChange={(v) => {
							if (v) onModelChange(v);
						}}
					>
						<Select.Trigger class="h-auto w-full cursor-pointer">
							<div class="flex items-center gap-2">
								<span class="font-medium">{selectedModelInfo?.label || selectedModel}</span>
								{#if selectedModelInfo?.active_format}
									<span class="text-xs text-muted-foreground">· {formatBackend(selectedModelInfo.active_format)}</span>
								{/if}
							</div>
						</Select.Trigger>
						<Select.Content>
							{#each installedModels as model (model.name)}
								<Select.Item value={model.name} label={model.label}>
									<div class="flex w-full items-center justify-between gap-3">
										<div class="flex flex-col">
											<span class="font-medium">{model.label}</span>
											<span class="text-[11px] text-muted-foreground">
												{formatBackend(model.active_format)}
												{#if model.fps_estimate}
													 · ~{model.fps_estimate} fps
												{/if}
											</span>
										</div>
									</div>
								</Select.Item>
							{/each}
						</Select.Content>
					</Select.Root>
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
							<p>Higher FPS provides real-time detection but uses more resources</p>
							<p>Lower FPS reduces load but detects less frequently</p>
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
						class="h-7 w-16 px-1 text-center font-mono text-xs"
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
							<p>Higher threshold shows only confident detections, reducing false alarms</p>
							<p>Lower threshold shows more detections but may include false positives</p>
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
						class="h-8 w-16 px-1 text-center font-mono text-xs"
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
							<p>Zone-based: Define specific areas for detection with custom rules</p>
							<p>Full frame: Detect objects across the entire video</p>
						</Tooltip.Content>
					</Tooltip.Root>
				</div>

				<Tabs.Root bind:value={activeTab} class="w-full">
					<Tabs.List class="w-full">
						<Tabs.Trigger value="zone-based" class="flex-1 cursor-pointer">Zone based</Tabs.Trigger>
						<Tabs.Trigger value="full-frame" class="flex-1 cursor-pointer">Full frame</Tabs.Trigger>
					</Tabs.List>

					<div class="mt-2 rounded-xl border border-border p-1.5">
						<Tabs.Content value="zone-based">
							<div class="flex min-h-0 flex-1 flex-col gap-2">
								<ToggleGroup.Root
									type="single"
									value={drawingMode}
									onValueChange={(v) => v && onDrawingModeChange(v as 'polygon' | 'line')}
									class="w-full justify-stretch"
									variant="outline"
								>
									<ToggleGroup.Item value="polygon" aria-label="Zone" class="flex-1 cursor-pointer gap-2">
										<Square class="h-4 w-4" />
										Zone
									</ToggleGroup.Item>
									<ToggleGroup.Item value="line" aria-label="Line" class="flex-1 cursor-pointer gap-2">
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
													{@const zoneColor = zone.color || '#fbbd05'}
													<!-- Zone Item -->
													<div
														class={cn(
															'group flex flex-col rounded-lg border bg-muted transition-all duration-150'
														)}
														style={selectedZoneId === zone.id
															? `border-color: ${hexToRgba(zoneColor, 0.5)};`
															: ''}
													>
														<!-- Header Row -->
														<!-- svelte-ignore a11y_click_events_have_key_events -->
														<!-- svelte-ignore a11y_no_static_element_interactions -->
														<div
															class="flex cursor-pointer items-center gap-2.5 px-2.5 py-2"
															onclick={() => onZoneSelected(zone.id)}
														>
															<div
																class="h-2.5 w-2.5 shrink-0 rounded-full transition-colors"
																style={selectedZoneId === zone.id
																	? `background-color: ${zoneColor};`
																	: `background-color: ${hexToRgba(zoneColor, 0.5)};`}
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
																		class="block cursor-pointer truncate text-sm font-medium"
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
																class="shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px]"
																style="background-color: {hexToRgba(
																	zoneColor,
																	0.2
																)}; color: {zoneColor};"
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
																					<button
																						type="button"
																						class="group/tag inline-flex cursor-pointer items-center gap-0.5 rounded bg-secondary px-1 py-0.5 font-mono text-[10px] text-secondary-foreground hover:bg-destructive/20 hover:text-destructive"
																						onclick={(e) => {
																							e.stopPropagation();
																							e.preventDefault();
																							onZoneClassesChanged(zone.id, zone.classes.filter((c) => c !== cls));
																						}}
																					>
																						{cls}
																						<X class="size-3 opacity-50 group-hover/tag:opacity-100" />
																					</button>
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
																				class="flex-1 cursor-pointer gap-1 rounded-[4px] font-mono text-[10px] data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
																			>
																				<ArrowUpDown class="h-3 w-3" />
																				A ↔ B
																			</ToggleGroup.Item>
																			<ToggleGroup.Item
																				value="in"
																				aria-label="A → B"
																				class="flex-1 cursor-pointer gap-1 rounded-[4px] font-mono text-[10px] data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
																			>
																				<ArrowDown class="h-3 w-3" />
																				A → B
																			</ToggleGroup.Item>
																			<ToggleGroup.Item
																				value="out"
																				aria-label="B → A"
																				class="flex-1 cursor-pointer gap-1 rounded-[4px] font-mono text-[10px] data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
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
															<button
																type="button"
																class="group/tag inline-flex cursor-pointer items-center gap-0.5 rounded bg-secondary px-1 py-0.5 font-mono text-[10px] text-secondary-foreground hover:bg-destructive/20 hover:text-destructive"
																onclick={(e) => {
																	e.stopPropagation();
																	e.preventDefault();
																	onFullFrameClassesChanged(fullFrameClasses.filter((c) => c !== cls));
																}}
															>
																{cls}
																<X class="size-3 opacity-50 group-hover/tag:opacity-100" />
															</button>
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
			class="h-10 w-full cursor-pointer text-sm"
			disabled={(activeTab === 'zone-based' && zones.length === 0) ||
				installedModels.length === 0 ||
				!selectedModel}
			onclick={() => onProcess(activeTab)}
		>
			Process
		</Button>
	</div>
</Card.Root>
