"use client";

import { Button } from "@hukuk/ui";
import { createApiClient } from "@hukuk/web-core/api/client";
import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { useErrorMessage } from "@hukuk/web-core/hooks/use-error-message";
import { useTranslations } from "next-intl";
import { useMemo, useState } from "react";

import { answerPlainText } from "@/lib/answer-text";
import { postFeedback } from "@/lib/chat-client";
import type { Answer } from "@/lib/chat-types";
import { FeedbackDialog } from "./feedback-dialog";

/** Under every answer: thumbs up and down, "Hata bildir", and copying the answer as plain text. */
export function FeedbackBar({ turnId, answer }: { turnId: string; answer: Answer }) {
    const t = useTranslations("chat.feedback");
    const errorMessage = useErrorMessage();
    const api = useMemo(() => createApiClient(), []);
    const [dialog, setDialog] = useState<"down" | "report" | null>(null);
    const [sent, setSent] = useState(false);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function rateUp() {
        setError(null);
        try {
            await postFeedback(api, turnId, { rating: "up", comment: "", correction: "" });
            setSent(true);
        } catch (failure) {
            setError(errorMessage(failure instanceof ApiFailure ? failure.code : undefined));
        }
    }

    async function copy() {
        await navigator.clipboard.writeText(
            answerPlainText(answer, {
                basis: t("copyText.basis"),
                conditional: t("copyText.conditional"),
                missing: t("copyText.missing"),
            }),
        );
        setCopied(true);
    }

    return (
        <div className="grid gap-2">
            <div role="group" aria-label={t("label")} className="flex flex-wrap items-center gap-2">
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label={t("up")}
                    onClick={rateUp}
                >
                    <span aria-hidden="true">{t("thumbUp")}</span>
                </Button>
                <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    aria-label={t("down")}
                    onClick={() => setDialog("down")}
                >
                    <span aria-hidden="true">{t("thumbDown")}</span>
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setDialog("report")}>
                    {t("report")}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={copy}>
                    {copied ? t("copied") : t("copy")}
                </Button>
            </div>
            <div role="status" className="text-sm text-ink-2">
                {sent ? t("sent") : null}
            </div>
            <div role="alert">{error ? <p className="text-sm text-low">{error}</p> : null}</div>
            <FeedbackDialog
                open={dialog !== null}
                rating={dialog === "down" ? "down" : null}
                turnId={turnId}
                points={answer.points}
                onClose={() => setDialog(null)}
                onSent={() => {
                    setDialog(null);
                    setSent(true);
                }}
            />
        </div>
    );
}
