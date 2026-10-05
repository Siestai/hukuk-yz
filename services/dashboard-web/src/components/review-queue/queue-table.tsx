import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { detailHref, PAGE_SIZE, type QueueParams } from "@/lib/queue-params";
import { useQueueItemFormat, type QueueItem } from "./queue-item-format";
import { ConfidenceChip, DuplicateIcon, ReasonChips, stretchedLink } from "./queue-item-parts";

export type { QueueItem } from "./queue-item-format";

export function QueueTable({ items, params }: { items: QueueItem[]; params: QueueParams }) {
    const t = useTranslations("review.queue.table");
    const format = useQueueItemFormat();

    return (
        <Table aria-label={t("label")}>
            <TableHeader>
                <TableRow className="hover:bg-surface-2">
                    <TableHead>{t("confidence")}</TableHead>
                    <TableHead>{t("decision")}</TableHead>
                    <TableHead>{t("court")}</TableHead>
                    <TableHead>{t("numbers")}</TableHead>
                    <TableHead>{t("date")}</TableHead>
                    <TableHead>{t("issue")}</TableHead>
                    <TableHead>{t("reasons")}</TableHead>
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
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}
