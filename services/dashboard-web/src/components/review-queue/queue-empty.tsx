import { Card, CardContent } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { hasFilters, queueHref, type QueueParams } from "@/lib/queue-params";

/** Nothing to show: the queue is empty, the filters match nothing, or the page is past the last. */
export function QueueEmpty({ params, pastEnd }: { params: QueueParams; pastEnd: boolean }) {
    const t = useTranslations("review.queue");
    const firstPage = queueHref({ ...params, page: 1 });
    const cleared = queueHref({ sort: params.sort, page: 1 });
    const linkClass = "text-sm font-medium text-primary underline";

    return (
        <Card>
            <CardContent className="grid justify-items-center gap-3 p-10 text-center">
                {pastEnd ? (
                    <>
                        <p className="text-ink">{t("empty.pastEnd")}</p>
                        <Link href={firstPage} className={linkClass}>
                            {t("empty.firstPage")}
                        </Link>
                    </>
                ) : hasFilters(params) ? (
                    <>
                        <p className="text-ink">{t("empty.filtered")}</p>
                        <Link href={cleared} className={linkClass}>
                            {t("filters.clear")}
                        </Link>
                    </>
                ) : (
                    <p className="text-ink">{t("empty.none")}</p>
                )}
            </CardContent>
        </Card>
    );
}
