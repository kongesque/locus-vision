import type { Handle } from '@sveltejs/kit';
import { redirect } from '@sveltejs/kit';
import { API_BASE } from '$lib/server/api';

/** Routes that don't require authentication */
const PUBLIC_PATHS = ['/login', '/signup', '/get-started', '/logout'];

export const handle: Handle = async ({ event, resolve }) => {
	// Default: no user
	event.locals.user = null;

	// Read access token from cookie
	const accessToken = event.cookies.get('access_token');

	if (accessToken) {
		try {
			const res = await fetch(`${API_BASE}/api/auth/me`, {
				headers: { Authorization: `Bearer ${accessToken}` }
			});

			if (res.ok) {
				const userData = await res.json();
				event.locals.user = {
					id: userData.id,
					email: userData.email,
					name: userData.name,
					role: userData.role
				};
			} else if (res.status === 401) {
				// Access token expired — try refresh
				const refreshToken = event.cookies.get('refresh_token');
				if (refreshToken) {
					const refreshRes = await fetch(`${API_BASE}/api/auth/refresh`, {
						method: 'POST',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ refresh_token: refreshToken })
					});

					if (refreshRes.ok) {
						const tokens = await refreshRes.json();

						// Set new cookies
						event.cookies.set('access_token', tokens.access_token, {
							path: '/',
							httpOnly: true,
							sameSite: 'lax',
							secure: event.url.protocol === 'https:',
							maxAge: 60 * 15 // 15 minutes
						});

						if (tokens.refresh_token) {
							event.cookies.set('refresh_token', tokens.refresh_token, {
								path: '/',
								httpOnly: true,
								sameSite: 'lax',
								secure: event.url.protocol === 'https:',
								maxAge: 60 * 60 * 24 * 7 // 7 days
							});
						}

						// Re-fetch user with new token
						const userRes = await fetch(`${API_BASE}/api/auth/me`, {
							headers: { Authorization: `Bearer ${tokens.access_token}` }
						});

						if (userRes.ok) {
							const userData = await userRes.json();
							event.locals.user = {
								id: userData.id,
								email: userData.email,
								name: userData.name,
								role: userData.role
							};
						}
					} else {
						// Refresh failed — clear cookies
						event.cookies.delete('access_token', { path: '/' });
						event.cookies.delete('refresh_token', { path: '/' });
					}
				}
			}
		} catch {
			// FastAPI not reachable — silently continue without auth
		}
	}

	const path = event.url.pathname;
	const isPublicPath = PUBLIC_PATHS.some((p) => path === p || path.startsWith(p + '/'));

	// Auth guard: redirect unauthenticated users to login (ALL routes protected)
	if (!event.locals.user && !isPublicPath) {
		// Check if setup is needed first
		try {
			const setupRes = await fetch(`${API_BASE}/api/auth/setup-status`);
			if (setupRes.ok) {
				const { needs_setup } = await setupRes.json();
				if (needs_setup) {
					throw redirect(303, '/get-started');
				}
			}
		} catch (e) {
			if (e instanceof Response || (e && typeof e === 'object' && 'status' in e)) throw e;
			// FastAPI not available — let the page load anyway
		}

		throw redirect(303, '/login');
	}

	// Redirect authenticated users away from auth pages
	if (event.locals.user && isPublicPath && !path.startsWith('/logout')) {
		throw redirect(303, '/');
	}

	return resolve(event);
};
