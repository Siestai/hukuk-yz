import { Badge, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { detailHref, type QueueParams } from "@/lib/queue-params";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

export type QueueItem = components["schemas"]["ReviewListItem"];

const MAX_REASON_CHIPS = 2;

// The title link stretches over its row (`after:absolute after:inset-0` on a `relative` row), so
// the whole row is one click target while keyboard and screen readers still get a single link.
// Tradeoff: text in the row cannot be selected with the mouse. Anything else interactive in a
// cell (a tooltip, a future link or button) needs `relative z-10` to sit above the overlay.
function DuplicateIcon({ label }: { label: string }) {
    return (
        <svg
            role="img"
            aria-label={label}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className="relative z-10 size-4 shrink-0 text-medium"
        >
            <title>{label}</title>
            <rect x={9} y={9} width={11} height={11} rx={2} />
            <path d="M5 15V6a2 2 0 0 1 2-2h9" />
        </svg>
    );
}

export function QueueTable({ items, params }: { items: QueueItem[]; params: QueueParams }) {
    const t = useTranslations("review.queue.table");
    const format = useFormatter();
    const labels = useEnumLabels();

    const { date } = useDates();
    const { empty, separator } = useCommon();
    const numbers = (item: QueueItem) =>
        [
            item.esas_no && t("esas", { value: item.esas_no }),
            item.karar_no && t("karar", { value: item.karar_no }),
        ]
            .filter(Boolean)
            .join(separator) || empty;
    const reasonLabel = (reason: string) => (
        <li key={reason}>
            <Badge
                variant="outline"
                title={labels.isKnownReason(reason) ? undefined : t("unknownReason")}
            >
                {labels.reason(reason)}
                {labels.isKnownReason(reason) ? null : (
                    <span className="sr-only">{t("unknownReason")}</span>
                )}
            </Badge>
        </li>
    );

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
                {items.map((item) => {
                    const rest = item.reasons.slice(MAX_REASON_CHIPS);
                    return (
                        <TableRow key={item.extraction_id} className="relative">
                            <TableCell>
                                <div className="flex items-center gap-2">
                                    <Badge variant={item.band}>{labels.band(item.band)}</Badge>
                                    <span className="font-mono text-xs text-ink-2">
                                        {format.number(item.score, "score")}
                                    </span>
                                </div>
                            </TableCell>
                            <TableCell className="max-w-96 py-2">
                                <div className="flex items-start gap-2">
                                    <div className="min-w-0">
                                        <p className="line-clamp-2 font-medium text-ink">
                                            <Link
                                                href={detailHref(item.extraction_id, params)}
                                                title={item.title}
                                                className="after:absolute after:inset-0 hover:underline focus-visible:underline"
                                            >
                                                {item.title}
                                            </Link>
                                        </p>
                                        {item.chamber ? (
                                            <p className="text-xs text-ink-3">{item.chamber}</p>
                                        ) : null}
                                    </div>
                                    {item.duplicate_group ? (
                                        <DuplicateIcon label={t("duplicate")} />
                                    ) : null}
                                </div>
                            </TableCell>
                            <TableCell className="whitespace-nowrap text-ink-2">
                                {labels.court(item.court)}
                            </TableCell>
                            <TableCell className="whitespace-nowrap font-mono text-xs">
                                {numbers(item)}
                            </TableCell>
                            <TableCell className="whitespace-nowrap font-mono text-xs">
                                {date(item.decision_date)}
                            </TableCell>
                            <TableCell className="font-mono text-xs">
                                {item.journal_issue ?? empty}
                            </TableCell>
                            <TableCell>
                                <ul className="flex gap-1">
                                    {item.reasons.slice(0, MAX_REASON_CHIPS).map(reasonLabel)}
                                    {rest.length > 0 ? (
                                        <li>
                                            <Badge
                                                variant="outline"
                                                aria-describedby={`${item.extraction_id}-more`}
                                            >
                                                +{format.number(rest.length, "integer")}
                                            </Badge>
                                            <ul
                                                id={`${item.extraction_id}-more`}
                                                className="sr-only"
                                            >
                                                {rest.map((reason) => (
                                                    <li key={reason}>{labels.reason(reason)}</li>
                                                ))}
                                            </ul>
                                        </li>
                                    ) : null}
                                </ul>
                            </TableCell>
                        </TableRow>
                    );
                })}
            </TableBody>
        </Table>
    );
}
