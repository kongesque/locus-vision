import { fail, redirect } from '@sveltejs/kit';
import { API_BASE } from '$lib/server/api';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	if (locals.user) {
		throw redirect(303, '/');
	}

	// Check if public signup is allowed
	try {
		const res = await fetch(`${API_BASE}/api/auth/signup-status`);
		if (res.ok) {
			const { allow_signup } = await res.json();
			if (!allow_signup) {
				throw redirect(303, '/login');
			}
		}
	} catch (e) {
		if (e && typeof e === 'object' && 'status' in e) throw e;
		// If we can't check, allow access (fail open for signup page)
	}
};

export const actions: Actions = {
	default: async ({ request, cookies, url }) => {
		const data = await request.formData();
		const name = data.get('name')?.toString() ?? '';
		const email = data.get('email')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';

		if (!name || !email || !password) {
			return fail(400, { error: 'All fields are required', name, email });
		}

		if (password.length < 8) {
			return fail(400, { error: 'Password must be at least 8 characters', name, email });
		}

		try {
			// Register the user
			const registerRes = await fetch(`${API_BASE}/api/auth/register`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name, email, password })
			});

			if (!registerRes.ok) {
				const body = await registerRes.json().catch(() => ({}));
				return fail(registerRes.status, {
					error: body.detail || 'Registration failed',
					name,
					email
				});
			}

			// Auto-login after registration
			const loginRes = await fetch(`${API_BASE}/api/auth/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password })
			});

			if (loginRes.ok) {
				const tokens = await loginRes.json();

				cookies.set('access_token', tokens.access_token, {
					path: '/',
					httpOnly: true,
					sameSite: 'lax',
					secure: url.protocol === 'https:',
					maxAge: 60 * 15
				});

				if (tokens.refresh_token) {
					cookies.set('refresh_token', tokens.refresh_token, {
						path: '/',
						httpOnly: true,
						sameSite: 'lax',
						secure: url.protocol === 'https:',
						maxAge: 60 * 60 * 24 * 7
					});
				}
			}
		} catch {
			return fail(500, { error: 'Unable to connect to server', name, email });
		}

		throw redirect(303, '/');
	}
};
