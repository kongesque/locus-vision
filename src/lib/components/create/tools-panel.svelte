<script lang="ts" module>
	export const YOLO_MODELS = [
		{ value: 'yolo11n', label: 'YOLO11 Nano', description: 'Fastest' },
		{ value: 'yolo11s', label: 'YOLO11 Small', description: 'Fast' },
		{ value: 'yolo11m', label: 'YOLO11 Medium', description: 'Balanced' },
		{ value: 'yolo11l', label: 'YOLO11 Large', description: 'Accurate' },
		{ value: 'yolo11x', label: 'YOLO11 XLarge', description: 'Most accurate' }
	] as const;

	export type YoloModel = (typeof YOLO_MODELS)[number]['value'];
</script>

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

	// Icons
	import { Trash2, Slash, Square, X, Info, Check, ChevronsUpDown } from '@lucide/svelte';

	import { cn } from '$lib/utils';
	import type { Zone } from './drawing-canvas.svelte';
	import { COCO_CLASSES } from '$lib/coco-classes';
	import { tick } from 'svelte';

	interface Props {
		zones: Zone[];
		selectedZoneId: string | null;
		drawingMode: 'polygon' | 'line';
		fullFrameClasses: string[];
		selectedModel: YoloModel;
		onDrawingModeChange: (mode: 'polygon' | 'line') => void;
		onZoneSelected: (id: string | null) => void;
		onDeleteZone: (id: string, e: MouseEvent) => void;
		onProcess: () => void;
		onZoneRenamed: (id: string, name: string) => void;
		onZoneClassesChanged: (id: string, classes: string[]) => void;
		onFullFrameClassesChanged: (classes: string[]) => void;
		onModelChange: (model: YoloModel) => void;
	}

	let {
		zones,
		selectedZoneId,
		drawingMode,
		fullFrameClasses,
		selectedModel,
		onDrawingModeChange,
		onZoneSelected,
		onDeleteZone,
		onProcess,
		onZoneRenamed,
		onZoneClassesChanged,
		onFullFrameClassesChanged,
		onModelChange
	}: Props = $props();

	let editingId = $state<string | null>(null);
	let tempName = $state('');

	// Combobox states
	let openZoneCombobox = $state<string | null>(null); // zone id
	let openFullFrameCombobox = $state(false);

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

<Card.Root class="flex flex-1 flex-col gap-4 p-4">
	<h3 class="font-semibold">Create</h3>
	<Separator />

	<!-- Model Selection -->
	<div>
		<div class="mb-2 flex items-center justify-between">
			<div class="font-semibold text-foreground">Model</div>
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
				if (v) onModelChange(v as YoloModel);
			}}
		>
			<Select.Trigger class="h-auto w-full">
				<span>{YOLO_MODELS.find((m) => m.value === selectedModel)?.label || 'Select model'}</span>
			</Select.Trigger>
			<Select.Content>
				{#each YOLO_MODELS as model}
					<Select.Item value={model.value} label={model.label}>
						<div class="flex items-center gap-2">
							<span class="font-medium">{model.label}</span>
							<span class="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
								>{model.description}</span
							>
						</div>
					</Select.Item>
				{/each}
			</Select.Content>
		</Select.Root>
	</div>

	<!-- Tools & Zones -->
	<div>
		<div class="mb-2 flex items-center justify-between">
			<div class="font-semibold text-foreground">Tools</div>
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

		<Tabs.Root value="zone-based" class="w-full">
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

	<div class="mt-auto pt-4">
		<Separator class="my-4" />
		<Button class="h-12 w-full" disabled={zones.length === 0} onclick={onProcess}>Process</Button>
	</div>
</Card.Root>
