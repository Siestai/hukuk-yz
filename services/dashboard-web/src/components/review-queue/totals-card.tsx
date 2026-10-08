import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import Link from "next/link";
import { HelpTip } from "@/components/help-tip";
import { stateHref, stateTab, type QueueState } from "@/lib/queue-state";
import { useFormatter, useTranslations } from "next-intl";

const DECISIONS: QueueState = { sort: "score_asc", page: 1 };
const linkClass =
    "inline-flex items-center text-ink-2 underline-offset-2 hover:underline pointer-coarse:min-h-11";

/** The results of the reviews so far; each count leads to its tab of the list. */
export function TotalsCard({
    approved,
    rejected,
    params = DECISIONS,
}: {
    approved: number;
    rejected: number;
    /** The queue whose tabs the counts lead to (the decision queue by default). */
    params?: QueueState;
}) {
    const tab = (status: "approved" | "rejected") => stateHref(stateTab(params, status));
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
