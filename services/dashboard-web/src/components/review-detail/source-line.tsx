import { useTranslations } from "next-intl";

import type { components } from "@hukuk/web-core/api/schema";
import { webLink } from "@/lib/files";
import { readJournal } from "@/lib/journal-scans";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

export type SourceProps = Pick<
    components["schemas"]["ReviewDetail"],
    "origin" | "scanned_at" | "journal"
>;

/**
 * Where the record came from: for a journal scan the time of the scan, the issue and a link to the
 * journal page; for an upload or the archive only the name of the source (the API gives no more).
 */
export function SourceLine({ origin, scanned_at: scannedAt, journal }: SourceProps) {
    const t = useTranslations("review.detail.source");
    const labels = useEnumLabels();
    const { dateTime } = useDates();
    if (origin !== "journal_scan") {
        return (
            <p className="text-sm text-ink-2">{t("plain", { origin: labels.origin(origin) })}</p>
        );
    }
    const { issueNo, pageUrl } = readJournal(journal);
    const link = pageUrl ? webLink(pageUrl) : null;
    const date = scannedAt ? dateTime(scannedAt) : null;
    const text =
        date && issueNo !== undefined
            ? t("scan", { date, issue: issueNo })
            : date
              ? t("scanNoIssue", { date })
              : labels.origin(origin);
    return (
        <p className="flex flex-wrap items-center gap-x-3 text-sm text-ink-2">
            <span>{text}</span>
            {link ? (
                <a
                    href={link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center py-2 font-medium text-primary underline pointer-coarse:min-h-11"
                >
                    {t("journalPage")}
                </a>
            ) : null}
        </p>
    );
}
