<script>
	import { AspectRatio } from '$lib/components/ui/aspect-ratio';
</script>

<div class="flex flex-1 flex-col gap-4 p-4">
	<div class="flex flex-1 flex-row gap-4">
		<div class="flex w-full max-w-4xl flex-col gap-4">
			<!-- Video Player - Simplified to standard browser controls -->
			<div class="relative overflow-hidden rounded-lg border bg-black shadow-sm">
				<AspectRatio ratio={16 / 9} class="max-h-[70vh]">
					<!-- TODO: Add video source from /create/[taskId] -->
					<video src="" class="h-full w-full object-contain" controls loop></video>
				</AspectRatio>
			</div>
		</div>
	</div>
</div>
