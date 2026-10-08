import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { TimelineVersion } from "@/lib/statute-as-of";
import { readEvidence, readFootnotes } from "@/lib/statute-timeline";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { UnknownCode } from "@/components/review-detail/unknown-code";
import { useRange } from "./use-range";
import { useLawLabel } from "./use-law-label";
import { VersionDiff } from "./version-diff";

function Box({ title, children }: { title: string; children: React.ReactNode }) {
    return (
        <section className="grid gap-2 rounded-md border border-border bg-surface-2 p-3 text-sm">
            <h3 className="text-xs font-medium tracking-wide text-ink-2">{title}</h3>
            {children}
        </section>
    );
}

/**
 * The selected version: its full text and heading as stored, the footnotes and the evidence in
 * boxes of their own, and the difference to the previous version.
 */
export function VersionPanel({
    version,
    previous,
    gapBetween,
}: {
    version: TimelineVersion;
    previous: TimelineVersion | null;
    gapBetween: boolean;
}) {
    const t = useTranslations("review.statutes.version");
    const labels = useEnumLabels();
    const range = useRange();
    const lawLabel = useLawLabel();
    const { date } = useDates();
    const evidence = readEvidence(version);
    const footnotes = readFootnotes(version);

    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex flex-wrap items-center gap-2">
                    {t("title", { range: range(version.valid_from, version.valid_to) })}
                    <Badge variant="outline">{labels.changeKind(version.change_kind)}</Badge>
                </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
                {version.heading ? (
                    <p className="text-sm text-ink-2">
                        <span className="font-medium">{t("heading")}:</span>{" "}
                        <span className="wrap-anywhere">{version.heading}</span>
                    </p>
                ) : null}
                <p className="font-serif leading-relaxed wrap-anywhere whitespace-pre-line text-ink">
                    {version.text}
                </p>
                {footnotes.length > 0 ? (
                    <Box title={t("footnotes")}>
                        <ol className="grid gap-2">
                            {footnotes.map((note) => (
                                <li
                                    key={`${note.no}-${note.text}`}
                                    className="wrap-anywhere text-ink-2"
                                >
                                    <span className="font-mono text-xs">{note.no}</span> {note.text}
                                </li>
                            ))}
                        </ol>
                    </Box>
                ) : null}
                <Box title={t("evidence")}>
                    <dl className="grid gap-2">
                        <div>
                            <dt className="text-ink-3">{t("basis")}</dt>
                            <dd className="text-ink">
                                {evidence.basis
                                    ? labels.evidenceBasis(evidence.basis)
                                    : t("unknown")}
                            </dd>
                        </div>
                        {evidence.amendments.length > 0 ? (
                            <div>
                                <dt className="text-ink-3">{t("amendments")}</dt>
                                <dd>
                                    <ul className="grid gap-0.5 text-ink">
                                        {evidence.amendments.map((ref) => (
                                            <li key={`${ref.law}-${ref.kabul}`}>
                                                {ref.kabul
                                                    ? t("amendment", {
                                                          law: lawLabel(ref.law),
                                                          date: date(ref.kabul),
                                                      })
                                                    : lawLabel(ref.law)}
                                            </li>
                                        ))}
                                    </ul>
                                </dd>
                            </div>
                        ) : null}
                        <div>
                            <dt className="text-ink-3">{t("copies")}</dt>
                            <dd>
                                <ul className="grid gap-0.5 text-ink">
                                    {evidence.copies.map((copy) => (
                                        <li key={copy.fileName} className="wrap-anywhere">
                                            {copy.date
                                                ? t("copy", {
                                                      name: copy.fileName,
                                                      date: date(copy.date),
                                                  })
                                                : copy.fileName}
                                        </li>
                                    ))}
                                </ul>
                            </dd>
                        </div>
                    </dl>
                </Box>
                {version.warnings.length > 0 ? (
                    <Box title={t("warnings")}>
                        <ul className="grid gap-1 text-ink-2">
                            {version.warnings.map((warning) => (
                                <li key={warning}>
                                    {labels.statuteWarning(warning)}
                                    <UnknownCode known={labels.isKnownStatuteWarning(warning)} />
                                </li>
                            ))}
                        </ul>
                    </Box>
                ) : null}
                <section className="grid gap-2" aria-labelledby="version-diff-title">
                    <h3 id="version-diff-title" className="text-sm font-medium text-ink">
                        {t("diff")}
                    </h3>
                    <VersionDiff version={version} previous={previous} gapBetween={gapBetween} />
                </section>
            </CardContent>
        </Card>
    );
}
