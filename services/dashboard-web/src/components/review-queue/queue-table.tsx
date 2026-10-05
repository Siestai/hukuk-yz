import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
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

export type { QueueItem } from "./queue-item-format";

export function QueueTable({ items, params }: { items: QueueItem[]; params: QueueParams }) {
    const t = useTranslations("review.queue.table");
    const format = useQueueItemFormat();
    const status = statusOf(params);
    const extras = EXTRAS[status];
    const columns: { label: string; help: HelpName }[] = [
        { label: t("confidence"), help: "colConfidence" },
        { label: t("decision"), help: "colDecision" },
        { label: t("court"), help: "colCourt" },
        { label: t("numbers"), help: "colNumbers" },
        { label: t("date"), help: "colDate" },
        { label: t("issue"), help: "colIssue" },
        { label: t("reasons"), help: "colReasons" },
        ...(extras.includes("status") ? [{ label: t("status"), help: "colStatus" as const }] : []),
        ...(extras.includes("review") ? [{ label: t("review"), help: "colReview" as const }] : []),
        ...(extras.includes("note") ? [{ label: t("note"), help: "colNote" as const }] : []),
    ];

    return (
        <Table aria-label={status === "pending" ? t("label") : t(`labels.${status}`)}>
            <TableHeader>
                <TableRow className="hover:bg-surface-2">
                    {columns.map(({ label, help }) => (
                        <TableHead key={help}>
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
                        <TableCell>
                            <ConfidenceChip item={item} format={format} />
                        </TableCell>
                        <TableCell className="max-w-96 py-2">
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
                                    {item.chamber ? (
                                        <p className="text-xs text-ink-3">{item.chamber}</p>
                                    ) : null}
                                </div>
                                {item.duplicate_group ? (
                                    <DuplicateIcon label={format.duplicateLabel} />
                                ) : null}
                            </div>
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-ink-2">
                            {format.court(item.court)}
                        </TableCell>
                        <TableCell className="whitespace-nowrap font-mono text-xs">
                            {format.numbers(item)}
                        </TableCell>
                        <TableCell className="whitespace-nowrap font-mono text-xs">
                            {format.date(item)}
                        </TableCell>
                        <TableCell className="font-mono text-xs">{format.issue(item)}</TableCell>
                        <TableCell>
                            <ReasonChips item={item} format={format} />
                        </TableCell>
                        {extras.includes("status") ? (
                            <TableCell>
                                <StatusBadge item={item} format={format} />
                            </TableCell>
                        ) : null}
                        {extras.includes("review") ? (
                            <TableCell className="text-xs">
                                <p className="whitespace-nowrap text-ink-2">
                                    {format.reviewedAt(item)}
                                </p>
                                <p className="text-ink-3">{format.reviewer(item)}</p>
                            </TableCell>
                        ) : null}
                        {extras.includes("note") ? (
                            <TableCell className="max-w-64 text-xs text-ink-2">
                                <p
                                    className="line-clamp-2 wrap-anywhere"
                                    title={item.note ?? undefined}
                                >
                                    {format.note(item)}
                                </p>
                            </TableCell>
                        ) : null}
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}
