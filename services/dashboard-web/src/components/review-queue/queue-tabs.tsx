import { cn } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import { HelpTip } from "@/components/help-tip";
import {
    queueHref,
    STATUSES,
    statusOf,
    tabParams,
    type QueueParams,
    type QueueStatus,
} from "@/lib/queue-params";

const HELP = {
    pending: "tabPending",
    approved: "tabApproved",
    rejected: "tabRejected",
    all: "tabAll",
} as const;

/**
 * The status tabs of the list. They are links that load another URL, so this is a navigation
 * landmark with `aria-current="page"` on the open one, not the ARIA tab pattern. A tab keeps the
 * filters and takes the sort of its own (`tabParams`). The tips sit beside the links, not in them.
 */
export function QueueTabs({
    params,
    counts,
}: {
    params: QueueParams;
    counts: Record<QueueStatus, number>;
}) {
    const t = useTranslations("review.queue.tabs");
    const format = useFormatter();
    const current = statusOf(params);

    return (
        <nav aria-label={t("label")}>
            <ul className="flex flex-wrap gap-x-2 gap-y-1 border-b border-border">
                {STATUSES.map((status) => (
                    <li key={status} className="flex items-center gap-1">
                        <Link
                            href={queueHref(tabParams(params, status))}
                            aria-current={status === current ? "page" : undefined}
                            className={cn(
                                "-mb-px inline-flex items-center gap-2 border-b-2 px-2 py-2 text-sm font-medium pointer-coarse:min-h-11",
                                status === current
                                    ? "border-primary text-primary"
                                    : "border-transparent text-ink-2 hover:text-ink",
                            )}
                        >
                            {t(status)}
                            <span className="font-mono text-xs">
                                {format.number(counts[status], "integer")}
                            </span>
                        </Link>
                        <HelpTip name={HELP[status]} topic={t(status)} />
                    </li>
                ))}
            </ul>
        </nav>
    );
}
