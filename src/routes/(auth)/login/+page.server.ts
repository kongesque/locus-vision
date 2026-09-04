import { fail, redirect } from '@sveltejs/kit';
import { API_BASE } from '$lib/server/api';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ locals }) => {
	// Redirect if already logged in
	if (locals.user) {
		throw redirect(303, '/');
	}

	// Check if public signup is allowed
	let allowSignup = false;
	try {
		const res = await fetch(`${API_BASE}/api/auth/signup-status`);
		if (res.ok) {
			const data = await res.json();
			allowSignup = data.allow_signup;
		}
	} catch {
		// If backend is unavailable, default to hidden
	}

	return { allowSignup };
};

export const actions: Actions = {
	default: async ({ request, cookies, url }) => {
		const data = await request.formData();
		const email = data.get('email')?.toString() ?? '';
		const password = data.get('password')?.toString() ?? '';

		if (!email || !password) {
			return fail(400, { error: 'Email and password are required', email });
		}

		try {
			const res = await fetch(`${API_BASE}/api/auth/login`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ email, password })
			});

			if (!res.ok) {
				const body = await res.json().catch(() => ({}));
				return fail(res.status, {
					error: body.detail || 'Invalid email or password',
					email
				});
			}

			const tokens = await res.json();

			// Set HttpOnly cookies
			cookies.set('access_token', tokens.access_token, {
				path: '/',
				httpOnly: true,
				sameSite: 'lax',
				secure: url.protocol === 'https:',
				maxAge: 60 * 15 // 15 minutes
			});

			if (tokens.refresh_token) {
				cookies.set('refresh_token', tokens.refresh_token, {
					path: '/',
					httpOnly: true,
					sameSite: 'lax',
					secure: url.protocol === 'https:',
					maxAge: 60 * 60 * 24 * 7 // 7 days
				});
			}
		} catch {
			return fail(500, { error: 'Unable to connect to server', email });
		}

		throw redirect(303, '/');
	}
};
