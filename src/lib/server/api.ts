import { env } from '$env/dynamic/private';
import type { Cookies } from '@sveltejs/kit';

export const API_BASE = env.LOCUS_API_URL || 'http://127.0.0.1:8000';

export function authenticatedApiFetch(
	cookies: Cookies,
	path: string,
	init: RequestInit = {}
): Promise<Response> {
	const headers = new Headers(init.headers);
	const accessToken = cookies.get('access_token');
	if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);

	return fetch(`${API_BASE}${path}`, { ...init, headers });
}
