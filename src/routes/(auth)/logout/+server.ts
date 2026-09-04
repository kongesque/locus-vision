import { redirect } from '@sveltejs/kit';
import { API_BASE } from '$lib/server/api';
import type { RequestHandler } from './$types';

export const POST: RequestHandler = async ({ cookies }) => {
    const accessToken = cookies.get('access_token');

    // Tell FastAPI to invalidate sessions
    if (accessToken) {
        try {
            await fetch(`${API_BASE}/api/auth/logout`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${accessToken}` }
            });
        } catch {
            // Ignore errors — we still clear cookies
        }
    }

    // Clear cookies
    cookies.delete('access_token', { path: '/' });
    cookies.delete('refresh_token', { path: '/' });

    throw redirect(303, '/login');
};
