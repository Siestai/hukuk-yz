import { cn, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { ReasonChips, stretchedLink } from "@/components/review-queue/queue-item-parts";
import { PAGE_SIZE } from "@/lib/queue-params";
import { statuteDetailHref, type StatuteQueueParams } from "@/lib/statute-queue-params";
import { useStatuteItemFormat, type StatuteItem } from "./statute-item-format";
import { StatuteBandBadge, StatuteStatusBadge } from "./statute-item-parts";

// Tighter cell padding than the default `px-3`, as in the decision table: it must fit without an inner scroll.
const cell = "px-2";

export function StatuteTable({
    items,
    params,
}: {
    items: StatuteItem[];
    params: StatuteQueueParams;
}) {
    const t = useTranslations("review.statutes.table");
    const format = useStatuteItemFormat();
    const columns = [
        t("band"),
        t("article"),
        t("versions"),
        t("snapshot"),
        t("reasons"),
        ...(params.status === undefined ? [] : [t("status")]),
    ];

    return (
        <Table aria-label={t("label")}>
            <TableHeader>
                <TableRow className="hover:bg-surface-2">
                    {columns.map((label) => (
                        <TableHead key={label} className={cell}>
                            {label}
                        </TableHead>
                    ))}
                </TableRow>
            </TableHeader>
            <TableBody>
                {items.map((item, index) => (
                    <TableRow key={item.extraction_id} className="relative">
                        <TableCell className={cell}>
                            <StatuteBandBadge item={item} format={format} />
                        </TableCell>
                        <TableCell className={cn(cell, "min-w-40 max-w-96 py-2")}>
                            <p className="line-clamp-2 font-medium wrap-anywhere text-ink">
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
                        </TableCell>
                        <TableCell className={cn(cell, "whitespace-nowrap text-xs text-ink-2")}>
                            {format.counts(item)}
                        </TableCell>
                        <TableCell className={cn(cell, "whitespace-nowrap font-mono text-xs")}>
                            {format.snapshot(item)}
                        </TableCell>
                        <TableCell className={cell}>
                            <ReasonChips item={item} format={format} wrap max={1} />
                        </TableCell>
                        {params.status === undefined ? null : (
                            <TableCell className={cn(cell, "py-2")}>
                                <StatuteStatusBadge item={item} format={format} />
                            </TableCell>
                        )}
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}
