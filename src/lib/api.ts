export const API_URL =
	typeof window !== 'undefined'
		? `${window.location.protocol}//${window.location.hostname}:8000`
		: 'http://127.0.0.1:8000';

export function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
	return fetch(`${API_URL}${path}`, { ...init, credentials: 'include' });
}
