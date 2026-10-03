import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { useDates } from "@/lib/use-dates";

type Review = components["schemas"]["ReviewOut"];

export function HistoryCard({ reviews }: { reviews: Review[] }) {
    const t = useTranslations();
    const { dateTime } = useDates();
    const fieldLabel = (name: string) => (t.has(`fields.${name}`) ? t(`fields.${name}`) : name);
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("review.detail.history.title")}</CardTitle>
            </CardHeader>
            <CardContent>
                {reviews.length === 0 ? (
                    <p className="text-sm text-ink-2">{t("review.detail.history.none")}</p>
                ) : (
                    <ol className="grid gap-3">
                        {reviews.map((review) => (
                            <li key={review.id} className="grid gap-1 text-sm">
                                <p className="text-ink">
                                    <span className="font-medium">{review.reviewer_name}</span>
                                    {" · "}
                                    {t(`review.detail.history.decision.${review.decision}`)}
                                </p>
                                <time dateTime={review.reviewed_at} className="text-xs text-ink-3">
                                    {dateTime(review.reviewed_at)}
                                </time>
                                {review.edits && Object.keys(review.edits).length > 0 ? (
                                    <p className="text-ink-2">
                                        {t("review.detail.history.edited", {
                                            fields: Object.keys(review.edits)
                                                .map(fieldLabel)
                                                .join(", "),
                                        })}
                                    </p>
                                ) : null}
                                {review.note ? <p className="text-ink-2">{review.note}</p> : null}
                            </li>
                        ))}
                    </ol>
                )}
            </CardContent>
        </Card>
    );
}
