import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { UnknownCode } from "@/components/review-detail/unknown-code";
import { useEnumLabels } from "@/lib/use-enum-labels";

type Props = { band: string; reasons: string[]; warnings: string[] };

function Sentences({ codes }: { codes: string[] }) {
    const labels = useEnumLabels();
    return (
        <ul className="grid gap-1 text-ink">
            {codes.map((code) => (
                <li key={code}>
                    {labels.statuteWarning(code)}
                    <UnknownCode known={labels.isKnownStatuteWarning(code)} />
                </li>
            ))}
        </ul>
    );
}

/**
 * The band of the article and why, in plain words: the reasons that lowered it and the other
 * warnings of the parser. A reason is also a warning, so it is not listed twice.
 */
export function StatuteConfidenceCard({ band, reasons, warnings }: Props) {
    const t = useTranslations("review.statutes.confidence");
    const labels = useEnumLabels();
    const others = warnings.filter((warning) => !reasons.includes(warning.split(":", 1)[0] ?? ""));
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm">
                <p className="flex items-center gap-2">
                    <span className="text-ink-3">{t("band")}</span>
                    <Badge variant={band === "high" || band === "medium" ? band : "low"}>
                        {labels.band(band)}
                    </Badge>
                </p>
                <section aria-labelledby="statute-reasons" className="grid gap-1">
                    <h3 id="statute-reasons" className="text-ink-3">
                        {t("reasons")}
                    </h3>
                    {reasons.length > 0 ? (
                        <Sentences codes={reasons} />
                    ) : (
                        <p className="text-ink-2">{t("noReasons")}</p>
                    )}
                </section>
                {others.length > 0 ? (
                    <section aria-labelledby="statute-warnings" className="grid gap-1">
                        <h3 id="statute-warnings" className="text-ink-3">
                            {t("warnings")}
                        </h3>
                        <Sentences codes={others} />
                    </section>
                ) : null}
            </CardContent>
        </Card>
    );
}
