import Link from "next/link";
import { useTranslations } from "next-intl";

import { SCAN_PAGE_SIZE, scanListHref } from "@/lib/journal-scans";

const linkClass =
    "inline-flex items-center text-sm font-medium text-primary underline pointer-coarse:min-h-11";

/** Previous / next page of the scan list; the list is paged by offset, so the total is known. */
export function ScanPagination({ page, total }: { page: number; total: number }) {
    const t = useTranslations("journalScans.list.pagination");
    const pageCount = Math.max(1, Math.ceil(total / SCAN_PAGE_SIZE));
    if (pageCount === 1) return null;
    return (
        <nav aria-label={t("label")} className="mt-4 flex items-center justify-between gap-4">
            {page > 1 ? (
                <Link href={scanListHref(page - 1)} className={linkClass}>
                    {t("previous")}
                </Link>
            ) : (
                <span />
            )}
            <p className="font-mono text-xs text-ink-2">
                {t("pageOf", { page, count: pageCount })}
            </p>
            {page < pageCount ? (
                <Link href={scanListHref(page + 1)} className={linkClass}>
                    {t("next")}
                </Link>
            ) : (
                <span />
            )}
        </nav>
    );
}
