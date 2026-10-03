import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

import { useEnumLabels } from "@/lib/use-enum-labels";

import { UnknownCode } from "./unknown-code";

type Props = { score: number; band: string; reasons: string[]; warnings: string[] };

export function ConfidenceCard({ score, band, reasons, warnings }: Props) {
    const t = useTranslations("review.detail");
    const format = useFormatter();
    const labels = useEnumLabels();
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("confidenceTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 text-sm">
                <dl className="flex gap-6">
                    <div>
                        <dt className="text-ink-3">{t("score")}</dt>
                        <dd className="font-mono text-ink">{format.number(score, "score")}</dd>
                    </div>
                    <div>
                        <dt className="text-ink-3">{t("band")}</dt>
                        <dd>
                            <Badge variant={band === "high" || band === "medium" ? band : "low"}>
                                {labels.band(band)}
                            </Badge>
                        </dd>
                    </div>
                </dl>
                <section aria-labelledby="detail-reasons" className="grid gap-1">
                    <h3 id="detail-reasons" className="text-ink-3">
                        {t("reasons")}
                    </h3>
                    {reasons.length > 0 ? (
                        <ul className="flex flex-wrap gap-1">
                            {reasons.map((reason) => (
                                <li key={reason}>
                                    <Badge variant="outline">
                                        {labels.reason(reason)}
                                        <UnknownCode known={labels.isKnownReason(reason)} />
                                    </Badge>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-ink-2">{t("noReasons")}</p>
                    )}
                </section>
                <section aria-labelledby="detail-warnings" className="grid gap-1">
                    <h3 id="detail-warnings" className="text-ink-3">
                        {t("warnings")}
                    </h3>
                    {warnings.length > 0 ? (
                        <ul className="flex flex-wrap gap-1">
                            {warnings.map((warning) => (
                                <li key={warning}>
                                    <Badge variant="outline">
                                        {labels.warning(warning)}
                                        <UnknownCode known={labels.isKnownWarning(warning)} />
                                    </Badge>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="text-ink-2">{t("noWarnings")}</p>
                    )}
                </section>
            </CardContent>
        </Card>
    );
}
