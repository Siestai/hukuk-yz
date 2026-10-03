import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { detailHref, type QueueParams } from "@/lib/queue-params";
import { useEnumLabels } from "@/lib/use-enum-labels";

type Props = { duplicates: components["schemas"]["DuplicateOut"][]; queue: QueueParams };

export function DuplicatesCard({ duplicates, queue }: Props) {
    const t = useTranslations("review.detail.duplicates");
    const format = useFormatter();
    const labels = useEnumLabels();
    if (duplicates.length === 0) return null;
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent>
                <ul className="grid gap-2">
                    {duplicates.map((duplicate) => (
                        <li
                            key={duplicate.extraction_id}
                            className="flex items-center gap-2 text-sm"
                        >
                            <Badge variant={duplicate.band}>{labels.band(duplicate.band)}</Badge>
                            <span className="font-mono text-xs text-ink-2">
                                {format.number(duplicate.score, "score")}
                            </span>
                            <Link
                                href={detailHref(duplicate.extraction_id, queue)}
                                className="text-primary hover:underline"
                            >
                                {t("item", { length: duplicate.text_length })}
                            </Link>
                        </li>
                    ))}
                </ul>
            </CardContent>
        </Card>
    );
}
