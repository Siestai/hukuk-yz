import Link from "next/link";
import { useTranslations } from "next-intl";

import { detailHref, PAGE_SIZE, type QueueParams } from "@/lib/queue-params";
import { useQueueItemFormat, type QueueItem } from "./queue-item-format";
import { ConfidenceChip, DuplicateIcon, ReasonChips, stretchedLink } from "./queue-item-parts";

/** The queue on a phone: the table's records as cards, one link each, fed by the same formatting. */
export function QueueCards({ items, params }: { items: QueueItem[]; params: QueueParams }) {
    const t = useTranslations("review.queue.table");
    const format = useQueueItemFormat();

    return (
        <ul aria-label={t("label")} className="grid gap-3">
            {items.map((item, index) => (
                <li
                    key={item.extraction_id}
                    className="relative grid gap-2 rounded-md border border-border bg-surface p-4 text-sm"
                >
                    <div className="flex items-center justify-between gap-2">
                        <ConfidenceChip item={item} format={format} />
                        {item.duplicate_group ? (
                            <DuplicateIcon label={format.duplicateLabel} />
                        ) : null}
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
                </li>
            ))}
        </ul>
    );
}
