"use client";

import { Button } from "@hukuk/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useErrorMessage } from "@/lib/use-error-message";
import { useReviewSession, type Failure } from "./review-session";

/** The field names of a 422 (`edits.karar_no` → `karar_no`); empty when the API named none. */
export function failedFields(failure: Failure | null): string[] {
    if (failure?.code !== "validation_error" || !Array.isArray(failure.params.fields)) return [];
    const names = failure.params.fields.flatMap((name: unknown) =>
        typeof name === "string" ? [name.replace(/^edits\./, "").split(".")[0] ?? ""] : [],
    );
    return [...new Set(names.filter(Boolean))];
}

/**
 * Which entries of `related_articles` a 422 names: `whole` when it names the list without an index,
 * and the indexes of `edits.related_articles.N.*`; the indexes are those of the list that was sent.
 */
export function failedArticleEntries(failure: Failure | null): {
    whole: boolean;
    entries: number[];
} {
    const names =
        failure?.code === "validation_error" && Array.isArray(failure.params.fields)
            ? failure.params.fields.filter(
                  (name: unknown): name is string => typeof name === "string",
              )
            : [];
    const indexes = names.flatMap((name) => {
        const match = /^(?:edits\.)?related_articles\.(\d+)(?:\.|$)/.exec(name);
        return match ? [Number(match[1])] : [];
    });
    return {
        whole: names.some((name) => /^(?:edits\.)?related_articles$/.test(name)),
        entries: [...new Set(indexes)],
    };
}

/** Why an action failed, by the API's error code. */
export function ActionFailure({ failure }: { failure: Failure }) {
    const t = useTranslations("review.actions");
    const message = useErrorMessage();
    const router = useRouter();
    const { queueHref } = useReviewSession();
    const conflicting = failure.params.decision_id;
    return (
        <div
            role="alert"
            className="grid gap-2 rounded-md border border-destructive bg-surface p-3 text-sm text-destructive"
            data-code={failure.code}
        >
            <p className="font-medium">{t("failureTitle")}</p>
            {failure.code === "review_conflict" ? (
                <>
                    <p>{message(failure.code)}</p>
                    <Button
                        variant="outline"
                        size="sm"
                        className="w-fit"
                        onClick={() => router.refresh()}
                    >
                        {t("refresh")}
                    </Button>
                </>
            ) : failure.code === "navigation_failed" ? (
                <>
                    <p>{t("navigationFailed")}</p>
                    <Link
                        href={queueHref}
                        className="inline-flex w-fit items-center font-medium underline pointer-coarse:min-h-11"
                    >
                        {t("toQueue")}
                    </Link>
                </>
            ) : failure.code === "decision_conflict" ? (
                <p>
                    {t("decisionConflict")}{" "}
                    {typeof conflicting === "string" ? (
                        <span className="font-mono text-xs wrap-anywhere">{conflicting}</span>
                    ) : null}
                </p>
            ) : failure.code === "validation_error" && failedFields(failure).length === 0 ? (
                <p>{t("publishRefused")}</p>
            ) : (
                <p>{message(failure.code, failure.params)}</p>
            )}
        </div>
    );
}
