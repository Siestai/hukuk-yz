import Link from "next/link";
import { useTranslations } from "next-intl";

import { stretchedLink } from "@/components/review-queue/queue-item-parts";
import { scanHref, SCAN_COUNTS, type JournalScanItem } from "@/lib/journal-scans";
import { useScanFormat } from "./scan-format";
import { ScanStatusBadge } from "./scan-status-badge";

/** The scan list below `xl`: the table's runs as cards, one link each, fed by the same formatting. */
export function ScanCards({ items }: { items: JournalScanItem[] }) {
    const t = useTranslations("journalScans.list.table");
    const format = useScanFormat();

    return (
        <ul aria-label={t("label")} className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {items.map((scan) => (
                <li
                    key={scan.id}
                    className="relative grid gap-2 rounded-md border border-border bg-surface p-4 text-sm"
                >
                    <div className="flex items-center justify-between gap-2">
                        <ScanStatusBadge status={scan.status} />
                        <span className="text-xs text-ink-2">{format.trigger(scan)}</span>
                    </div>
                    <p className="font-medium text-ink">
                        <Link href={scanHref(scan.id)} className={stretchedLink}>
                            {format.startedAt(scan)}
                        </Link>
                    </p>
                    <p className="text-xs text-ink-2">
                        {t("newIssues")}: {format.issues(scan.new_issues)}
                    </p>
                    <dl className="grid grid-cols-4 gap-2 text-xs">
                        {SCAN_COUNTS.map((key) => (
                            <div key={key} className="grid gap-0.5">
                                <dt className="text-ink-2">{t(key)}</dt>
                                <dd className="font-mono text-sm text-ink">
                                    {format.count(scan[key])}
                                </dd>
                            </div>
                        ))}
                    </dl>
                </li>
            ))}
        </ul>
    );
}
