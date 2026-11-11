import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { readWarning, splitFailure, type JournalScanDetail } from "@/lib/journal-scans";
import { useScanFormat } from "./scan-format";

/** What went wrong with the run as a whole: why it failed, and the report's warnings. */
export function ScanNotes({ report }: { report: JournalScanDetail["report"] }) {
    const t = useTranslations("journalScans.detail");
    const format = useScanFormat();
    const failure = report.failure ? splitFailure(report.failure) : null;
    const warnings = report.warnings.map((warning) => {
        const known = readWarning(warning);
        return known ? t("warnings.archive_max_above_site", { max: known.value }) : warning;
    });
    if (!failure && warnings.length === 0 && report.archive_max == null) return null;

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("notes.title")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
                {failure ? (
                    <div role="alert" className="grid gap-1 rounded-md bg-low-soft p-3 text-low">
                        <p className="font-medium">
                            {t("notes.failure", { reason: format.reason(failure.reason) })}
                        </p>
                        {failure.url ? (
                            <p className="font-mono text-xs wrap-anywhere">{failure.url}</p>
                        ) : null}
                    </div>
                ) : null}
                {report.archive_max != null ? (
                    <p className="text-ink-2">
                        {t("notes.archiveMax", { no: report.archive_max })}
                    </p>
                ) : null}
                {warnings.length > 0 ? (
                    <ul className="grid gap-1 text-medium">
                        {warnings.map((warning) => (
                            <li key={warning}>{warning}</li>
                        ))}
                    </ul>
                ) : null}
            </CardContent>
        </Card>
    );
}
