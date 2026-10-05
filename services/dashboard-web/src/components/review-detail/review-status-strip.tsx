"use client";

import { useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useReviewSession } from "./review-session";

type Review = components["schemas"]["ReviewOut"];

/**
 * The outcome of a record that left the queue, in one block: "Reddedildi · date · reviewer", the
 * rejection note and the sentence that the review actions are unavailable. A record that left
 * the queue without a review (published) shows its status and that sentence. Nothing for a record
 * still waiting. Such a record has no action bar, so the
 * "no next / previous record" message of the J / K keys is shown here.
 */
export function ReviewStatusStrip({
    sourceStatus,
    reviews,
}: {
    sourceStatus: string;
    reviews: Review[];
}) {
    const t = useTranslations();
    const { dateTime } = useDates();
    const { separator } = useCommon();
    const labels = useEnumLabels();
    const { edge, canAct } = useReviewSession();
    const last = reviews.at(-1);
    const left = sourceStatus !== "analyzed";
    const outcome =
        last?.decision === "reject" || sourceStatus === "rejected"
            ? "rejected"
            : last?.decision === "edit"
              ? "edited"
              : "approved";

    return (
        <>
            {left ? (
                <section
                    aria-label={t("review.detail.statusStrip.label")}
                    className="grid gap-1 rounded-md border border-border bg-surface-2 p-3 text-sm"
                >
                    <p className="text-ink">
                        <span className="font-medium">
                            {last
                                ? t(`review.detail.statusStrip.${outcome}`)
                                : labels.sourceStatus(sourceStatus)}
                        </span>
                        {last ? (
                            <>
                                {separator}
                                <time dateTime={last.reviewed_at}>
                                    {dateTime(last.reviewed_at)}
                                </time>
                                {separator}
                                {last.reviewer_name ?? t("review.detail.unknownReviewer")}
                            </>
                        ) : null}
                    </p>
                    {outcome === "rejected" && last?.note ? (
                        <p className="wrap-anywhere text-ink-2">
                            <span className="font-medium">
                                {t("review.detail.statusStrip.note")}:
                            </span>{" "}
                            {last.note}
                        </p>
                    ) : null}
                    <p className="text-ink-2">{t("review.detail.statusStrip.unavailable")}</p>
                </section>
            ) : null}
            {canAct ? null : (
                <div role="status" className="text-sm text-ink-2">
                    {edge === "next" ? t("review.actions.noNext") : null}
                    {edge === "previous" ? t("review.actions.noPrevious") : null}
                </div>
            )}
        </>
    );
}
