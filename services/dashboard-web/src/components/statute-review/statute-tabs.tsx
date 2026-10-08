import { cn } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import {
    statuteListHref,
    STATUTES,
    type StatuteNo,
    type StatuteQueueParams,
} from "@/lib/statute-queue-params";

/**
 * The statute tabs (4857, 5510) with the articles waiting in each. Links that load another URL,
 * so a navigation landmark with `aria-current="page"`, like the status tabs; a tab keeps the
 * status and filters and opens the first page.
 */
export function StatuteTabs({
    params,
    waiting,
}: {
    params: StatuteQueueParams;
    waiting: Record<StatuteNo, number>;
}) {
    const t = useTranslations("review.statutes.statuteTabs");
    const format = useFormatter();

    return (
        <nav aria-label={t("label")}>
            <ul className="flex flex-wrap gap-x-2 gap-y-1 border-b border-border">
                {STATUTES.map((statute) => (
                    <li key={statute}>
                        <Link
                            href={statuteListHref({ ...params, statute, page: 1 })}
                            aria-current={statute === params.statute ? "page" : undefined}
                            className={cn(
                                "-mb-px inline-flex items-center gap-2 border-b-2 px-2 py-2 text-sm font-medium pointer-coarse:min-h-11",
                                statute === params.statute
                                    ? "border-primary text-primary"
                                    : "border-transparent text-ink-2 hover:text-ink",
                            )}
                        >
                            {t(statute)}
                            <span className="font-mono text-xs">
                                {format.number(waiting[statute], "integer")}
                            </span>
                        </Link>
                    </li>
                ))}
            </ul>
        </nav>
    );
}
