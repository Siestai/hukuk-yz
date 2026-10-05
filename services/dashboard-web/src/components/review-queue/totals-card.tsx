import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { HelpTip } from "@/components/help-tip";
import { useFormatter, useTranslations } from "next-intl";

export function TotalsCard({ approved, rejected }: { approved: number; rejected: number }) {
    const t = useTranslations("review.queue.summary");
    const format = useFormatter();
    return (
        <Card>
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    {t("totalsTitle")}
                    <HelpTip name="totals" topic={t("totalsTitle")} />
                </CardTitle>
            </CardHeader>
            <CardContent>
                <dl className="grid gap-2 text-sm">
                    <div className="flex justify-between">
                        <dt className="text-ink-2">{t("approved")}</dt>
                        <dd className="font-mono text-high">
                            {format.number(approved, "integer")}
                        </dd>
                    </div>
                    <div className="flex justify-between">
                        <dt className="text-ink-2">{t("rejected")}</dt>
                        <dd className="font-mono text-low">{format.number(rejected, "integer")}</dd>
                    </div>
                </dl>
            </CardContent>
        </Card>
    );
}
