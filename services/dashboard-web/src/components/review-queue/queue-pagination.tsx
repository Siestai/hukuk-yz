import Link from "next/link";
import { useTranslations } from "next-intl";

import { cn } from "@hukuk/ui";
import { pageItems } from "@/lib/pagination";
import { PAGE_SIZE, queueHref, type QueueParams } from "@/lib/queue-params";

const pageClass = "inline-flex h-8 min-w-8 items-center justify-center rounded-md px-2 text-sm";

export function QueuePagination({ params, total }: { params: QueueParams; total: number }) {
    const t = useTranslations("review.queue.pagination");
    const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
    const href = (page: number) => queueHref({ ...params, page });
    const step = (label: string, page: number, enabled: boolean) =>
        enabled ? (
            <Link href={href(page)} className={cn(pageClass, "text-ink hover:bg-primary-soft")}>
                {label}
            </Link>
        ) : null;

    return (
        <div className="flex items-center justify-between gap-4 text-sm text-ink-2">
            <p className="font-mono text-xs">
                {t("range", {
                    from: (params.page - 1) * PAGE_SIZE + 1,
                    to: Math.min(params.page * PAGE_SIZE, total),
                    total,
                })}
            </p>
            <nav aria-label={t("label")} className="flex items-center gap-1">
                {step(t("previous"), params.page - 1, params.page > 1)}
                {pageItems(params.page, pageCount).map((item, index) =>
                    item === "gap" ? (
                        <span key={`gap-${index}`} aria-hidden="true" className={pageClass}>
                            …
                        </span>
                    ) : (
                        <Link
                            key={item}
                            href={href(item)}
                            aria-label={t("page", { page: item })}
                            aria-current={item === params.page ? "page" : undefined}
                            className={cn(
                                pageClass,
                                "font-mono",
                                item === params.page
                                    ? "bg-primary text-primary-foreground"
                                    : "text-ink hover:bg-primary-soft",
                            )}
                        >
                            {item}
                        </Link>
                    ),
                )}
                {step(t("next"), params.page + 1, params.page < pageCount)}
            </nav>
        </div>
    );
}
