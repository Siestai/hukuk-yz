export type PageItem = number | "gap";

/** Page numbers to show: first, last and the neighbours of the current page, with gaps between. */
export function pageItems(page: number, pageCount: number): PageItem[] {
    const wanted = new Set([1, pageCount, page - 1, page, page + 1]);
    const pages = [...wanted].filter((n) => n >= 1 && n <= pageCount).sort((a, b) => a - b);
    return pages.flatMap((n, i): PageItem[] => {
        const previous = pages[i - 1];
        if (previous === undefined || n === previous + 1) return [n];
        // An ellipsis for a single missing page would be longer than the page itself.
        return n === previous + 2 ? [previous + 1, n] : ["gap", n];
    });
}
