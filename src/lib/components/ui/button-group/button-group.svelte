<script lang="ts">
	import { cn } from '$lib/utils.js';

	let { class: className, orientation = 'horizontal', children, ...restProps } = $props();
</script>

<div
	class={cn('flex', orientation === 'vertical' ? 'flex-col' : 'flex-row', className)}
	{...restProps}
>
	{@render children?.()}
</div>
