import { cn } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import { changeFileParams, fileListHref, type FileListParams } from "@/lib/files";

/**
 * "Tümü" and "Onay bekliyor" with the number waiting. Links that load another URL, so a navigation
 * landmark with `aria-current="page"` on the open one, like the queue tabs; a tab keeps the filters.
 */
export function FileTabs({ params, pending }: { params: FileListParams; pending: number | null }) {
    const t = useTranslations("files.list.tabs");
    const format = useFormatter();
    const tabs = [
        { review: undefined, label: t("all"), count: null },
        { review: "pending", label: t("pending"), count: pending },
    ] as const;

    return (
        <nav aria-label={t("label")}>
            <ul className="flex flex-wrap gap-x-2 gap-y-1 border-b border-border">
                {tabs.map(({ review, label, count }) => (
                    <li key={label}>
                        <Link
                            href={fileListHref(changeFileParams(params, { review }))}
                            aria-current={review === params.review ? "page" : undefined}
                            className={cn(
                                "-mb-px inline-flex items-center gap-2 border-b-2 px-2 py-2 text-sm font-medium pointer-coarse:min-h-11",
                                review === params.review
                                    ? "border-primary text-primary"
                                    : "border-transparent text-ink-2 hover:text-ink",
                            )}
                        >
                            {label}
                            {count ? (
                                <span className="font-mono text-xs">
                                    {format.number(count, "integer")}
                                </span>
                            ) : null}
                        </Link>
                    </li>
                ))}
            </ul>
        </nav>
    );
}
