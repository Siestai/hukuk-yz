import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import Link from "next/link";
import { HelpTip } from "@/components/help-tip";
import { queueHref, tabParams } from "@/lib/queue-params";
import { useFormatter, useTranslations } from "next-intl";

const tab = (status: "approved" | "rejected") =>
    queueHref(tabParams({ sort: "score_asc", page: 1 }, status));
const linkClass =
    "inline-flex items-center text-ink-2 underline-offset-2 hover:underline pointer-coarse:min-h-11";

/** The results of the reviews so far; each count leads to its tab of the list. */
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
                        <dt>
                            <Link href={tab("approved")} className={linkClass}>
                                {t("approved")}
                            </Link>
                        </dt>
                        <dd className="font-mono text-high">
                            {format.number(approved, "integer")}
                        </dd>
                    </div>
                    <div className="flex justify-between">
                        <dt>
                            <Link href={tab("rejected")} className={linkClass}>
                                {t("rejected")}
                            </Link>
                        </dt>
                        <dd className="font-mono text-low">{format.number(rejected, "integer")}</dd>
                    </div>
                </dl>
            </CardContent>
        </Card>
    );
}
