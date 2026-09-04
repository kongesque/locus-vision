import { authenticatedApiFetch } from '$lib/server/api';
import type { PageServerLoad } from './$types';

export interface VideoTask {
	id: string;
	filename: string;
	status: string;
	progress: number;
	created_at: string;
	completed_at: string | null;
	duration: string | null;
	format: string | null;
	model_name: string | null;
	total_count: number | null;
	zone_counts: string | null;
	zones: string | null;
	error_message: string | null;
}

export const load: PageServerLoad = async ({ cookies }) => {
	try {
		const res = await authenticatedApiFetch(cookies, '/api/video/history');
		if (res.ok) {
			const history: VideoTask[] = await res.json();
			return { history };
		}
	} catch (error) {
		console.error('Failed to load video history:', error);
	}

	return { history: [] };
};
