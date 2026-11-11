import { cn, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { stretchedLink } from "@/components/review-queue/queue-item-parts";
import { scanHref, type JournalScanItem } from "@/lib/journal-scans";
import { useScanFormat } from "./scan-format";
import { ScanStatusBadge } from "./scan-status-badge";

const cell = "px-2";

/** The scan list from `xl`: a row is one run, the date links to its report. */
export function ScanTable({ items }: { items: JournalScanItem[] }) {
    const t = useTranslations("journalScans.list.table");
    const format = useScanFormat();
    const columns = [
        t("time"),
        t("trigger"),
        t("status"),
        t("newIssues"),
        t("discovered"),
        t("queued"),
        t("duplicates"),
        t("errors"),
    ];
    const numeric = "text-right font-mono text-xs";

    return (
        <Table aria-label={t("label")}>
            <TableHeader>
                <TableRow className="hover:bg-surface-2">
                    {columns.map((label, index) => (
                        <TableHead key={label} className={cn(cell, index >= 4 && "text-right")}>
                            {label}
                        </TableHead>
                    ))}
                </TableRow>
            </TableHeader>
            <TableBody>
                {items.map((scan) => (
                    <TableRow key={scan.id} className="relative">
                        <TableCell className={cn(cell, "whitespace-nowrap font-medium text-ink")}>
                            <Link href={scanHref(scan.id)} className={stretchedLink}>
                                {format.startedAt(scan)}
                            </Link>
                        </TableCell>
                        <TableCell className={cell}>{format.trigger(scan)}</TableCell>
                        <TableCell className={cell}>
                            <ScanStatusBadge status={scan.status} />
                        </TableCell>
                        <TableCell className={cn(cell, "font-mono text-xs")}>
                            {format.issues(scan.new_issues)}
                        </TableCell>
                        <TableCell className={cn(cell, numeric)}>
                            {format.count(scan.discovered)}
                        </TableCell>
                        <TableCell className={cn(cell, numeric)}>
                            {format.count(scan.queued)}
                        </TableCell>
                        <TableCell className={cn(cell, numeric)}>
                            {format.count(scan.duplicates)}
                        </TableCell>
                        <TableCell className={cn(cell, numeric)}>
                            {format.count(scan.errors)}
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}
