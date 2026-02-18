import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ cookies }) => {
    const colsCookie = cookies.get('livestream_cols');
    const defaultGridCols = colsCookie ? parseInt(colsCookie, 10) : 3;
    const safeGridCols = isNaN(defaultGridCols) ? 3 : defaultGridCols;

    return {
        initialGridCols: safeGridCols
    };
};
