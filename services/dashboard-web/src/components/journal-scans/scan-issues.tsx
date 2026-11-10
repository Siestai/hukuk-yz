import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { webLink } from "@/lib/files";
import { ISSUE_COUNTS, type JournalIssueReport } from "@/lib/journal-scans";
import { useScanFormat } from "./scan-format";

/** One card per journal issue the run looked at: the numbers, and the decisions that were not queued. */
export function ScanIssues({ issues }: { issues: JournalIssueReport[] }) {
    const t = useTranslations("journalScans.detail.issues");
    const format = useScanFormat();

    return (
        <section aria-labelledby="scan-issues" className="grid grid-cols-1 gap-4">
            <h2 id="scan-issues" className="text-lg font-semibold text-ink">
                {t("title")}
            </h2>
            {issues.length === 0 ? (
                <Card>
                    <CardContent className="p-6 text-sm text-ink-2">{t("none")}</CardContent>
                </Card>
            ) : (
                <ul className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                    {issues.map((issue) => (
                        <li key={issue.issue_no}>
                            <Card>
                                <CardHeader>
                                    <CardTitle>{format.issueName(issue.issue_no)}</CardTitle>
                                </CardHeader>
                                <CardContent className="grid gap-4">
                                    <dl className="grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
                                        {ISSUE_COUNTS.map((key) => (
                                            <div key={key} className="grid gap-0.5">
                                                <dt className="text-xs text-ink-2">{t(key)}</dt>
                                                <dd className="font-mono text-ink">
                                                    {format.count(issue[key])}
                                                </dd>
                                            </div>
                                        ))}
                                        {issue.duplicate_candidates > 0 ? (
                                            <div className="grid gap-0.5">
                                                <dt className="text-xs text-ink-2">
                                                    {t("duplicate_candidates")}
                                                </dt>
                                                <dd className="font-mono text-ink">
                                                    {format.count(issue.duplicate_candidates)}
                                                </dd>
                                            </div>
                                        ) : null}
                                    </dl>
                                    {issue.errors.length > 0 ? (
                                        <div className="grid gap-2">
                                            <h3 className="text-sm font-medium text-ink">
                                                {t("errors", { count: issue.errors.length })}
                                            </h3>
                                            <ul className="grid gap-2">
                                                {issue.errors.map((error) => {
                                                    const link = webLink(error.url);
                                                    return (
                                                        <li
                                                            key={`${error.url}|${error.reason}`}
                                                            className="grid gap-0.5 rounded-md bg-low-soft p-3 text-sm"
                                                        >
                                                            <span className="text-low">
                                                                {format.reason(error.reason)}
                                                            </span>
                                                            <span className="font-mono text-xs wrap-anywhere text-ink-2">
                                                                {link ? (
                                                                    <a
                                                                        href={link}
                                                                        target="_blank"
                                                                        rel="noopener noreferrer"
                                                                        className="underline"
                                                                    >
                                                                        {error.url}
                                                                    </a>
                                                                ) : (
                                                                    error.url
                                                                )}
                                                            </span>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                        </div>
                                    ) : null}
                                </CardContent>
                            </Card>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
