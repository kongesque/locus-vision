export const API_URL =
	typeof window !== 'undefined'
		? `${window.location.protocol}//${window.location.hostname}:8000`
		: 'http://127.0.0.1:8000';
