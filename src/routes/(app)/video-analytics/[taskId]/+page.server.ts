import { authenticatedApiFetch } from '$lib/server/api';
import type { PageServerLoad } from './$types';
import type { VideoTask } from '../+page.server';

export const load: PageServerLoad = async ({ params, cookies }) => {
	const taskId = params.taskId;

	try {
		const res = await authenticatedApiFetch(cookies, '/api/video/history');
		if (res.ok) {
			const history: VideoTask[] = await res.json();
			return {
				task: history.find((task) => task.id === taskId),
				taskId
			};
		}
	} catch (error) {
		console.error('Failed to load video task:', error);
	}

	return { task: null, taskId };
};
