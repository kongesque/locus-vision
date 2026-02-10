export const titleMap: Record<string, string> = {
    '/': 'Home',
    '/livestream': 'Live Stream',
    '/video-analytics': 'Video Analytics',
    '/settings': 'Settings'
};

export function getPageTitle(pathname: string): string {
    return titleMap[pathname] || 'Locus';
}
