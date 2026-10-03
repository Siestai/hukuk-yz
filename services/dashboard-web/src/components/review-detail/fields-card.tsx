import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import type { DecisionFields, RelatedArticle } from "@/lib/decision-fields";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

const EMPTY = "-";

function Row({ label, children }: { label: string; children: ReactNode }) {
    return (
        <div className="grid grid-cols-3 gap-2 border-b border-line-2 py-2 text-sm last:border-b-0">
            <dt className="text-ink-3">{label}</dt>
            <dd className="col-span-2 text-ink">{children}</dd>
        </div>
    );
}

function Mono({ value }: { value: string }) {
    return value ? <span className="font-mono text-xs">{value}</span> : EMPTY;
}

/** "4857 s. Kanun m. 18, 17/3"; a statute the parser could not map shows the line it read. */
function articleText(
    entry: RelatedArticle,
    t: (key: string, values: Record<string, string>) => string,
): string {
    if (entry.statute === null) return entry.raw || entry.label;
    const statute = String(entry.statute);
    return entry.articles.length > 0
        ? t("review.detail.article", { statute, articles: entry.articles.join(", ") })
        : t("review.detail.articleNoNumbers", { statute });
}

export function FieldsCard({ fields }: { fields: DecisionFields }) {
    const t = useTranslations();
    const labels = useEnumLabels();
    const { date } = useDates();
    const field = (name: string) => t(`fields.${name}`);
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("review.detail.fieldsTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
                <dl>
                    <Row label={field("court")}>
                        {fields.court ? labels.court(fields.court) : EMPTY}
                    </Row>
                    <Row label={field("court_level")}>
                        {fields.courtLevel ? labels.courtLevel(fields.courtLevel) : EMPTY}
                    </Row>
                    <Row label={field("chamber")}>{fields.chamber || EMPTY}</Row>
                    {fields.bamRegion ? (
                        <Row label={field("bam_region")}>{fields.bamRegion}</Row>
                    ) : null}
                    <Row label={field("esas_no")}>
                        <Mono value={fields.esasNo} />
                    </Row>
                    <Row label={field("karar_no")}>
                        <Mono value={fields.kararNo} />
                    </Row>
                    <Row label={field("decision_date")}>{date(fields.decisionDate)}</Row>
                    <Row label={field("related_articles")}>
                        {fields.relatedArticles.length > 0 ? (
                            <ul className="grid gap-1">
                                {fields.relatedArticles.map((entry, i) => (
                                    <li key={i}>{articleText(entry, t)}</li>
                                ))}
                            </ul>
                        ) : (
                            EMPTY
                        )}
                    </Row>
                    <Row label={field("outcome")}>
                        {fields.outcome ? labels.outcome(fields.outcome) : EMPTY}
                    </Row>
                    <Row label={field("keywords")}>
                        {fields.keywords.length > 0 ? (
                            <ul className="flex flex-wrap gap-1">
                                {fields.keywords.map((keyword) => (
                                    <li key={keyword}>
                                        <Badge variant="outline">{keyword}</Badge>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            EMPTY
                        )}
                    </Row>
                    <Row label={field("journal_issue")}>
                        <Mono
                            value={fields.journalIssue === null ? "" : String(fields.journalIssue)}
                        />
                    </Row>
                </dl>
            </CardContent>
        </Card>
    );
}
