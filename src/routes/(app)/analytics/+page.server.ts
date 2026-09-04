import { authenticatedApiFetch } from '$lib/server/api';
import type { PageServerLoad } from './$types';

interface Camera {
	id: string;
	name: string;
	status: string;
}

export const load: PageServerLoad = async ({ cookies, url }) => {
	const preselectedCamera = url.searchParams.get('camera') ?? undefined;

	try {
		const res = await authenticatedApiFetch(cookies, '/api/cameras');
		if (res.ok) {
			const allCameras: Camera[] = await res.json();
			return {
				cameras: allCameras.filter((camera) => camera.status === 'active'),
				preselectedCamera
			};
		}
	} catch (error) {
		console.error('Failed to load cameras for analytics', error);
	}

	return { cameras: [], preselectedCamera };
};
