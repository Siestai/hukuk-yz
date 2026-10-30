"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { type ReactNode, useRef, useState } from "react";

import type { components } from "@hukuk/web-core/api/schema";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useErrorMessage } from "@hukuk/web-core/hooks/use-error-message";
import { ReopenDialog } from "./reopen-dialog";
import { useReviewSession } from "./review-session";

type Review = components["schemas"]["ReviewOut"];

/**
 * The outcome of a record that left the queue, in one block: "Reddedildi · date · reviewer", the
 * rejection note and the sentence that the review actions are unavailable. A record that left
 * the queue without a review (published) shows its status and that sentence, and for a decision the
 * button that reopens it ("Onaydan çıkar" / "Reddi geri al"). Only a failed reopen shows for a
 * record that is waiting (it may have been reopened by someone else). Such a record has no action bar, so the
 * "no next / previous record" message of the J / K keys is shown here.
 */
export function ReviewStatusStrip({
    sourceStatus,
    reviews,
    help,
}: {
    sourceStatus: string;
    reviews: Review[];
    /** A tip about the statuses (the statute screen has one), beside the outcome. */
    help?: ReactNode;
}) {
    const t = useTranslations();
    const { dateTime } = useDates();
    const { separator } = useCommon();
    const labels = useEnumLabels();
    const message = useErrorMessage();
    const { edge, canAct, subject, failure, busy } = useReviewSession();
    const [reopening, setReopening] = useState(false);
    const reopenButton = useRef<HTMLButtonElement>(null);
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
                    <div className="flex items-start gap-2">
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
                        {help}
                    </div>
                    {outcome === "rejected" && last?.note ? (
                        <p className="wrap-anywhere text-ink-2">
                            <span className="font-medium">
                                {t("review.detail.statusStrip.note")}:
                            </span>{" "}
                            {last.note}
                        </p>
                    ) : null}
                    <p className="text-ink-2">{t("review.detail.statusStrip.unavailable")}</p>
                    {subject === "decision" ? (
                        <>
                            <Button
                                ref={reopenButton}
                                variant="outline"
                                className="w-full md:w-fit"
                                onClick={() => setReopening(true)}
                                disabled={busy}
                            >
                                {outcome === "rejected"
                                    ? t("review.reopen.fromRejected")
                                    : t("review.reopen.fromApproved")}
                            </Button>
                            <ReopenDialog
                                open={reopening}
                                onClose={() => setReopening(false)}
                                returnFocusTo={reopenButton}
                            />
                        </>
                    ) : null}
                </section>
            ) : null}
            {failure?.during === "reopen" && (!reopening || failure.code === "review_conflict") ? (
                <p
                    role="alert"
                    className="rounded-md border border-destructive bg-surface p-3 text-sm text-destructive"
                    data-code={failure.code}
                >
                    {failure.code === "review_conflict"
                        ? t("review.reopen.conflict")
                        : message(failure.code, failure.params)}
                </p>
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
