import { getTranslations } from "next-intl/server";

import { BulkApproveButton } from "@/components/review-queue/bulk-approve-button";
import type { components } from "@/lib/api/schema";
import type { Settled } from "@/lib/api/settle";
import { isNumberedArticle } from "@/lib/statute-article";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";

/** How many articles the dialog shows as examples. */
const SAMPLE_SIZE = 5;

/**
 * The bulk approve button of the statute queue, with the list it will confirm (as for decisions):
 * the pending count of the statute and band (the API's bulk scope knows no search) and the first
 * articles of the list response on screen.
 */
export async function StatuteBulkApprove({
    params,
    pending,
    list,
}: {
    params: StatuteQueueParams;
    /** The articles waiting in this statute and band (the summary), whatever the search: the count the API checks. */
    pending?: number;
    list?: Promise<Settled<components["schemas"]["StatuteReviewListResponse"]>>;
}) {
    const t = await getTranslations("review.statutes");
    const result = list ? await list : undefined;
    const data = result?.data;
    return (
        <BulkApproveButton
            params={params}
            unavailable={!data || pending === undefined}
            total={pending ?? 0}
            sample={(data?.items ?? []).slice(0, SAMPLE_SIZE).map((item) => ({
                id: item.extraction_id,
                title: item.heading
                    ? t("articleTitle", {
                          article: isNumberedArticle(item.article_no)
                              ? t("articleNo", { no: item.article_no })
                              : item.article_no,
                          heading: item.heading,
                      })
                    : isNumberedArticle(item.article_no)
                      ? t("articleNo", { no: item.article_no })
                      : item.article_no,
                esasNo: "",
                kararNo: "",
                note: t("item.counts", { versions: item.version_count, gaps: item.gap_count }),
            }))}
        />
    );
}
