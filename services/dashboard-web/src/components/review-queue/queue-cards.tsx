import Link from "next/link";
import { useTranslations } from "next-intl";

import { detailHref, PAGE_SIZE, statusOf, type QueueParams } from "@/lib/queue-params";
import { EXTRAS, useQueueItemFormat, type QueueItem } from "./queue-item-format";
import {
    ConfidenceChip,
    DuplicateIcon,
    ReasonChips,
    StatusBadge,
    stretchedLink,
} from "./queue-item-parts";

/** The queue below `lg`: the table's records as cards, one link each, fed by the same formatting. */
export function QueueCards({ items, params }: { items: QueueItem[]; params: QueueParams }) {
    const t = useTranslations("review.queue.table");
    const format = useQueueItemFormat();
    const status = statusOf(params);
    const extras = EXTRAS[status];

    return (
        <ul
            aria-label={status === "pending" ? t("label") : t(`labels.${status}`)}
            className="grid grid-cols-1 gap-3 md:grid-cols-2"
        >
            {items.map((item, index) => (
                <li
                    key={item.extraction_id}
                    className="relative grid gap-2 rounded-md border border-border bg-surface p-4 text-sm"
                >
                    <div className="flex items-center justify-between gap-2">
                        <ConfidenceChip item={item} format={format} />
                        <div className="flex items-center gap-2">
                            {extras.includes("status") ? (
                                <StatusBadge item={item} format={format} />
                            ) : null}
                            {item.duplicate_group ? (
                                <DuplicateIcon label={format.duplicateLabel} />
                            ) : null}
                        </div>
                    </div>
                    <p className="line-clamp-2 min-w-0 wrap-anywhere font-medium text-ink">
                        <Link
                            href={detailHref(item.extraction_id, params, {
                                pos: (params.page - 1) * PAGE_SIZE + index,
                            })}
                            title={item.title}
                            className={stretchedLink}
                        >
                            {item.title}
                        </Link>
                    </p>
                    <p className="text-xs text-ink-2">
                        {[format.court(item.court), item.chamber]
                            .filter(Boolean)
                            .join(format.separator)}
                    </p>
                    <p className="font-mono text-xs text-ink-2">
                        {format.numbers(item)}
                        {format.separator}
                        {format.date(item)}
                    </p>
                    <p className="text-xs text-ink-3">
                        {t("issueValue", { value: format.issue(item) })}
                    </p>
                    <ReasonChips item={item} format={format} wrap />
                    {extras.includes("review") && item.reviewed_at ? (
                        <p className="text-xs text-ink-3">
                            {format.reviewedOn(item)}
                            {format.separator}
                            {format.reviewer(item)}
                        </p>
                    ) : null}
                    {extras.includes("note") && item.note ? (
                        <p className="line-clamp-2 text-xs wrap-anywhere text-ink-2">
                            {format.noteLine(item)}
                        </p>
                    ) : null}
                </li>
            ))}
        </ul>
    );
}
