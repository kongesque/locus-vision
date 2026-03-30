import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, url }) => {
	const preselectedCamera = url.searchParams.get('camera') ?? undefined;
    // Let's fetch the available cameras to populate the dropdown
    try {
        const res = await fetch('http://127.0.0.1:8000/api/cameras');
        if (res.ok) {
            const cameras = await res.json();
            return { cameras, preselectedCamera };
        }
    } catch (e) {
        console.error('Failed to load cameras for analytics', e);
    }
    return { cameras: [], preselectedCamera };
};
