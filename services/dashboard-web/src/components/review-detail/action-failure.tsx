"use client";

import { Button } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { useErrorMessage } from "@/lib/use-error-message";
import type { Failure } from "./review-session";

/** The field names of a 422 (`edits.karar_no` → `karar_no`); empty when the API named none. */
export function failedFields(failure: Failure | null): string[] {
    if (failure?.code !== "validation_error" || !Array.isArray(failure.params.fields)) return [];
    const names = failure.params.fields.flatMap((name: unknown) =>
        typeof name === "string" ? [name.replace(/^edits\./, "").split(".")[0] ?? ""] : [],
    );
    return [...new Set(names.filter(Boolean))];
}

/** Why an action failed, by the API's error code. */
export function ActionFailure({ failure }: { failure: Failure }) {
    const t = useTranslations("review.actions");
    const message = useErrorMessage();
    const router = useRouter();
    const conflicting = failure.params.decision_id;
    return (
        <div
            role="alert"
            className="grid gap-2 rounded-md bg-low-soft p-3 text-sm text-low"
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
