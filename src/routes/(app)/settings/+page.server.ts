import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

const API_BASE = 'http://127.0.0.1:8000';

export const load: PageServerLoad = async ({ cookies, locals }) => {
    const accessToken = cookies.get('access_token');
    if (!accessToken || !locals.user) {
        throw redirect(303, '/login');
    }

    const isAdmin = locals.user.role === 'admin';

    let users: any[] = [];
    let appSettings = { allow_signup: false };
    let storageStats = null;

    if (isAdmin) {
        // Fetch all users
        const usersRes = await fetch(`${API_BASE}/api/admin/users`, {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        if (usersRes.ok) {
            users = await usersRes.json();
        }

        // Fetch app settings
        const settingsRes = await fetch(`${API_BASE}/api/admin/app-settings`, {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        if (settingsRes.ok) {
            appSettings = await settingsRes.json();
        }

        // Fetch storage stats
        const storageRes = await fetch(`${API_BASE}/api/admin/system/storage`, {
            headers: { Authorization: `Bearer ${accessToken}` }
        });
        if (storageRes.ok) {
            storageStats = await storageRes.json();
        }
    }

    // Fetch sessions
    const sessionsRes = await fetch(`${API_BASE}/api/settings/sessions`, {
        headers: { Authorization: `Bearer ${accessToken}` }
    });
    const sessions = sessionsRes.ok ? await sessionsRes.json() : [];

    return {
        user: locals.user,
        users,
        sessions,
        appSettings,
        storageStats
    };
};

export const actions: Actions = {
    updateAccount: async ({ request, cookies }) => {
        const data = await request.formData();
        const name = data.get('name') as string;
        const email = data.get('email') as string;
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/settings/account`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${accessToken}`
            },
            body: JSON.stringify({ name: name || undefined, email: email || undefined })
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { accountError: err.detail || 'Failed to update account' });
        }

        return { accountSuccess: true };
    },

    changePassword: async ({ request, cookies }) => {
        const data = await request.formData();
        const currentPassword = data.get('current_password') as string;
        const newPassword = data.get('new_password') as string;
        const confirmPassword = data.get('confirm_password') as string;
        const accessToken = cookies.get('access_token');

        if (newPassword !== confirmPassword) {
            return fail(400, { passwordError: 'New passwords do not match' });
        }

        const res = await fetch(`${API_BASE}/api/settings/password`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${accessToken}`
            },
            body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { passwordError: err.detail || 'Failed to change password' });
        }

        // Password changed — user needs to re-login since sessions were invalidated
        cookies.delete('access_token', { path: '/' });
        cookies.delete('refresh_token', { path: '/' });
        throw redirect(303, '/login');
    },

    revokeSessions: async ({ cookies }) => {
        const accessToken = cookies.get('access_token');

        await fetch(`${API_BASE}/api/settings/sessions`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${accessToken}` }
        });

        // Clear own cookies too
        cookies.delete('access_token', { path: '/' });
        cookies.delete('refresh_token', { path: '/' });
        throw redirect(303, '/login');
    },

    updateRole: async ({ request, cookies }) => {
        const data = await request.formData();
        const userId = data.get('user_id') as string;
        const role = data.get('role') as string;
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/admin/users/${userId}/role`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${accessToken}`
            },
            body: JSON.stringify({ role })
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { adminError: err.detail || 'Failed to update role' });
        }

        return { adminSuccess: true };
    },

    toggleUserActive: async ({ request, cookies }) => {
        const data = await request.formData();
        const userId = data.get('user_id') as string;
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/admin/users/${userId}/active`, {
            method: 'PUT',
            headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { adminError: err.detail || 'Failed to toggle user' });
        }

        return { adminSuccess: true };
    },

    deleteUser: async ({ request, cookies }) => {
        const data = await request.formData();
        const userId = data.get('user_id') as string;
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/admin/users/${userId}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { adminError: err.detail || 'Failed to delete user' });
        }

        return { adminSuccess: true };
    },

    toggleSignup: async ({ request, cookies }) => {
        const data = await request.formData();
        const allowSignup = data.get('allow_signup') === 'true';
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/admin/app-settings`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${accessToken}`
            },
            body: JSON.stringify({ allow_signup: allowSignup })
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { adminError: err.detail || 'Failed to update signup setting' });
        }

        return { settingsSuccess: true };
    },

    deleteAllMedia: async ({ cookies }) => {
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/admin/media`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { adminError: err.detail || 'Failed to delete media' });
        }

        return { adminSuccess: true, message: 'All media and stream configurations deleted successfully' };
    },

    deleteAccount: async ({ cookies }) => {
        const accessToken = cookies.get('access_token');

        const res = await fetch(`${API_BASE}/api/settings/account`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${accessToken}` }
        });

        if (!res.ok) {
            const err = await res.json();
            return fail(res.status, { accountError: err.detail || 'Failed to delete account' });
        }

        // Account deleted successfully, now logout the user
        cookies.delete('access_token', { path: '/' });
        cookies.delete('refresh_token', { path: '/' });
        throw redirect(303, '/login');
    }
};
