// Derives the backend API base URL from the browser's current location.
// - In the browser: uses the same hostname/protocol the user is accessing from,
//   so it works on localhost, LAN IPs, Tailscale, or any other host without config.
// - On the server (SSR/actions): uses the container-internal loopback address.
export const API_URL =
	typeof window !== 'undefined'
		? `${window.location.protocol}//${window.location.hostname}:8000`
		: 'http://127.0.0.1:8000';
