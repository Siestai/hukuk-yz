"use client";

import { useTranslations } from "next-intl";

import type { components } from "@/lib/api/schema";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useReviewSession } from "./review-session";

type Review = components["schemas"]["ReviewOut"];

/**
 * The outcome of a record that was already reviewed: "Reddedildi · date · reviewer" with the
 * rejection note. Nothing for a record still waiting. Such a record has no action bar, so the
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
    const { edge, canAct } = useReviewSession();
    const last = reviews.at(-1);
    const reviewed = sourceStatus !== "analyzed" && last;
    const outcome =
        last?.decision === "reject" || sourceStatus === "rejected"
            ? "rejected"
            : last?.decision === "edit"
              ? "edited"
              : "approved";

    return (
        <>
            {reviewed ? (
                <section
                    aria-label={t("review.detail.statusStrip.label")}
                    className="grid gap-1 rounded-md border border-border bg-surface-2 p-3 text-sm"
                >
                    <p className="text-ink">
                        <span className="font-medium">
                            {t(`review.detail.statusStrip.${outcome}`)}
                        </span>
                        {separator}
                        <time dateTime={last.reviewed_at}>{dateTime(last.reviewed_at)}</time>
                        {separator}
                        {last.reviewer_name ?? t("review.detail.unknownReviewer")}
                    </p>
                    {outcome === "rejected" && last.note ? (
                        <p className="wrap-anywhere text-ink-2">
                            <span className="font-medium">
                                {t("review.detail.statusStrip.note")}:
                            </span>{" "}
                            {last.note}
                        </p>
                    ) : null}
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
