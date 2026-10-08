import { Card, CardContent } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { statuteListHref, type StatuteQueueParams } from "@/lib/statute-queue-params";

/** Nothing to show: no article waits, the filters match nothing, or the page is past the last. */
export function StatuteEmpty({
    params,
    pastEnd,
}: {
    params: StatuteQueueParams;
    pastEnd: boolean;
}) {
    const t = useTranslations("review");
    const filtered = Boolean(params.band || params.q);
    const linkClass =
        "inline-flex items-center text-sm font-medium text-primary underline pointer-coarse:min-h-11";

    return (
        <Card>
            <CardContent className="grid justify-items-center gap-3 p-10 text-center">
                {pastEnd ? (
                    <>
                        <p className="text-ink">{t("queue.empty.pastEnd")}</p>
                        <Link href={statuteListHref({ ...params, page: 1 })} className={linkClass}>
                            {t("queue.empty.firstPage")}
                        </Link>
                    </>
                ) : filtered ? (
                    <>
                        <p className="text-ink">{t("queue.empty.filtered")}</p>
                        <Link
                            href={statuteListHref({
                                kind: "statute",
                                statute: params.statute,
                                status: params.status,
                                page: 1,
                            })}
                            className={linkClass}
                        >
                            {t("queue.filters.clear")}
                        </Link>
                    </>
                ) : (
                    <p className="text-ink">{t(`statutes.empty.${params.status ?? "pending"}`)}</p>
                )}
            </CardContent>
        </Card>
    );
}
