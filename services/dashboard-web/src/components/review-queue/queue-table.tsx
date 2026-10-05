import { cn, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { HelpTip } from "@/components/help-tip";
import type { HelpName } from "@/lib/help-topics";
import { detailHref, PAGE_SIZE, statusOf, type QueueParams } from "@/lib/queue-params";
import { EXTRAS, useQueueItemFormat, type QueueItem } from "./queue-item-format";
import {
    ConfidenceChip,
    DuplicateIcon,
    ReasonChips,
    StatusBadge,
    stretchedLink,
} from "./queue-item-parts";

// Tighter cell padding than the default `px-3`: the table sits beside the side column from `xl`
// and its columns must fit 960 px without an inner scroll.
const cell = "px-2";

export type { QueueItem } from "./queue-item-format";

export function QueueTable({ items, params }: { items: QueueItem[]; params: QueueParams }) {
    const t = useTranslations("review.queue.table");
    const format = useQueueItemFormat();
    const status = statusOf(params);
    const extras = EXTRAS[status];
    const columns: { label: string; help: HelpName }[] = [
        { label: t("confidence"), help: "colConfidence" },
        { label: t("decision"), help: "colDecision" },
        { label: t("numbers"), help: "colNumbers" },
        { label: t("date"), help: "colDate" },
        { label: t("issue"), help: "colIssue" },
        { label: t("reasons"), help: "colReasons" },
        ...(extras.length > 0 ? [{ label: t("status"), help: "colStatus" as const }] : []),
    ];

    return (
        <Table aria-label={status === "pending" ? t("label") : t(`labels.${status}`)}>
            <TableHeader>
                <TableRow className="hover:bg-surface-2">
                    {columns.map(({ label, help }) => (
                        <TableHead key={help} className={cell}>
                            <span className="inline-flex items-center gap-1.5">
                                {label}
                                <HelpTip name={help} topic={label} />
                            </span>
                        </TableHead>
                    ))}
                </TableRow>
            </TableHeader>
            <TableBody>
                {items.map((item, index) => (
                    <TableRow key={item.extraction_id} className="relative">
                        <TableCell className={cell}>
                            <ConfidenceChip item={item} format={format} />
                        </TableCell>
                        <TableCell className={cn(cell, "min-w-40 max-w-96 py-2")}>
                            <div className="flex items-start gap-2">
                                <div className="min-w-0">
                                    <p className="line-clamp-2 font-medium text-ink">
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
                                    <p className="text-xs text-ink-3">
                                        {[format.court(item.court), item.chamber]
                                            .filter(Boolean)
                                            .join(format.separator)}
                                    </p>
                                </div>
                                {item.duplicate_group ? (
                                    <DuplicateIcon label={format.duplicateLabel} />
                                ) : null}
                            </div>
                        </TableCell>
                        <TableCell className={cn(cell, "font-mono text-xs")}>
                            {item.esas_no || item.karar_no ? (
                                <>
                                    {item.esas_no ? (
                                        <p className="whitespace-nowrap">
                                            {t("esas", { value: item.esas_no })}
                                        </p>
                                    ) : null}
                                    {item.karar_no ? (
                                        <p className="whitespace-nowrap">
                                            {t("karar", { value: item.karar_no })}
                                        </p>
                                    ) : null}
                                </>
                            ) : (
                                format.empty
                            )}
                        </TableCell>
                        <TableCell className={cn(cell, "whitespace-nowrap font-mono text-xs")}>
                            {format.date(item)}
                        </TableCell>
                        <TableCell className={cn(cell, "font-mono text-xs")}>
                            {format.issue(item)}
                        </TableCell>
                        <TableCell className={cell}>
                            <ReasonChips item={item} format={format} wrap max={1} />
                        </TableCell>
                        {extras.length > 0 ? (
                            <TableCell className={cn(cell, "py-2")}>
                                <StatusBadge item={item} format={format} />
                                {extras.includes("review") && item.reviewed_at ? (
                                    <p className="mt-1 text-xs text-ink-2">
                                        {format.reviewedAt(item)}
                                        {format.separator}
                                        {format.reviewer(item)}
                                    </p>
                                ) : null}
                                {extras.includes("note") && item.note ? (
                                    <p
                                        className="line-clamp-1 max-w-56 text-xs wrap-anywhere text-ink-3"
                                        title={item.note}
                                    >
                                        {format.noteLine(item)}
                                    </p>
                                ) : null}
                            </TableCell>
                        ) : null}
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}
