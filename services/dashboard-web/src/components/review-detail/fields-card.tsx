import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { type DecisionFields, esasDisplay, type RelatedArticle } from "@/lib/decision-fields";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";

/** Values are stored text of any length: they wrap inside the card instead of widening it. */
function Row({ label, children }: { label: string; children: ReactNode }) {
    return (
        <div className="grid grid-cols-3 gap-2 border-b border-line-2 py-2 text-sm last:border-b-0">
            <dt className="min-w-0 wrap-anywhere text-ink-3">{label}</dt>
            <dd className="col-span-2 min-w-0 wrap-anywhere text-ink">{children}</dd>
        </div>
    );
}

function Mono({ value }: { value: string }) {
    const { empty } = useCommon();
    return value ? <span className="font-mono text-xs">{value}</span> : empty;
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
    const { empty } = useCommon();
    const field = (name: string) => t(`fields.${name}`);
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("review.detail.fieldsTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
                <dl>
                    <Row label={field("court")}>
                        {fields.court ? labels.court(fields.court) : empty}
                    </Row>
                    <Row label={field("court_level")}>
                        {fields.courtLevel ? labels.courtLevel(fields.courtLevel) : empty}
                    </Row>
                    <Row label={field("chamber")}>{fields.chamber || empty}</Row>
                    {fields.bamRegion ? (
                        <Row label={field("bam_region")}>{fields.bamRegion}</Row>
                    ) : null}
                    <Row label={field("esas_no")}>
                        <Mono value={esasDisplay(fields)} />
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
                            empty
                        )}
                    </Row>
                    <Row label={field("outcome")}>
                        {fields.outcome ? labels.outcome(fields.outcome) : empty}
                    </Row>
                    <Row label={field("keywords")}>
                        {fields.keywords.length > 0 ? (
                            <ul className="flex min-w-0 flex-wrap gap-1">
                                {fields.keywords.map((keyword, i) => (
                                    <li key={i} className="min-w-0 max-w-full">
                                        <Badge
                                            variant="outline"
                                            className="max-w-full whitespace-normal wrap-anywhere"
                                        >
                                            {keyword}
                                        </Badge>
                                    </li>
                                ))}
                            </ul>
                        ) : (
                            empty
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
