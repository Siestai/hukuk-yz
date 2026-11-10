import { Button, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { queueHref } from "@/lib/queue-params";
import { SCAN_COUNTS, type JournalScanDetail } from "@/lib/journal-scans";
import { useScanFormat } from "./scan-format";

/** The run in numbers, and the way to its decisions in the review queue. */
export function ScanSummary({ scan }: { scan: JournalScanDetail }) {
    const t = useTranslations("journalScans");
    const format = useScanFormat();
    const rows = [
        { label: t("detail.summary.startedAt"), value: format.startedAt(scan) },
        { label: t("detail.summary.finishedAt"), value: format.finishedAt(scan) },
        { label: t("list.table.newIssues"), value: format.issues(scan.new_issues) },
        { label: t("detail.summary.downloaded"), value: format.count(scan.downloaded) },
        ...SCAN_COUNTS.map((key) => ({
            label: t(`list.table.${key}`),
            value: format.count(scan[key]),
        })),
    ];

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("detail.summary.title")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
                <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
                    {rows.map(({ label, value }) => (
                        <div key={label} className="grid gap-0.5">
                            <dt className="text-xs text-ink-2">{label}</dt>
                            <dd className="font-mono wrap-anywhere text-ink">{value}</dd>
                        </div>
                    ))}
                </dl>
                <Button asChild className="w-full md:w-fit">
                    <Link
                        href={queueHref({
                            status: "all",
                            jobId: scan.job_id,
                            sort: "reviewed_desc",
                            page: 1,
                        })}
                    >
                        {t("detail.summary.decisions")}
                    </Link>
                </Button>
            </CardContent>
        </Card>
    );
}
