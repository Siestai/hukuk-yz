import Link from "next/link";
import { useTranslations } from "next-intl";

import { ReasonChips, stretchedLink } from "@/components/review-queue/queue-item-parts";
import { PAGE_SIZE } from "@/lib/queue-params";
import { statuteDetailHref, type StatuteQueueParams } from "@/lib/statute-queue-params";
import { useStatuteItemFormat, type StatuteItem } from "./statute-item-format";
import { StatuteBandBadge, StatuteStatusBadge } from "./statute-item-parts";

/** The queue below `xl`: the table's articles as cards, one link each, fed by the same formatting. */
export function StatuteCards({
    items,
    params,
}: {
    items: StatuteItem[];
    params: StatuteQueueParams;
}) {
    const t = useTranslations("review.statutes.table");
    const format = useStatuteItemFormat();

    return (
        <ul aria-label={t("label")} className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {items.map((item, index) => (
                <li
                    key={item.extraction_id}
                    className="relative grid gap-2 rounded-md border border-border bg-surface p-4 text-sm"
                >
                    <div className="flex items-center justify-between gap-2">
                        <StatuteBandBadge item={item} format={format} />
                        {params.status === undefined ? null : (
                            <StatuteStatusBadge item={item} format={format} />
                        )}
                    </div>
                    <p className="line-clamp-2 min-w-0 wrap-anywhere font-medium text-ink">
                        <Link
                            href={statuteDetailHref(item.extraction_id, params, {
                                pos: (params.page - 1) * PAGE_SIZE + index,
                            })}
                            title={format.title(item)}
                            className={stretchedLink}
                        >
                            {format.title(item)}
                        </Link>
                    </p>
                    <p className="text-xs text-ink-2">
                        {format.counts(item)}
                        {format.separator}
                        {t("snapshotValue", { date: format.snapshot(item) })}
                    </p>
                    <ReasonChips item={item} format={format} wrap />
                </li>
            ))}
        </ul>
    );
}
