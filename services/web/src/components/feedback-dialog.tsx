"use client";

import { Button, Dialog, DialogActions, Label, Select, Textarea } from "@hukuk/ui";
import { createApiClient } from "@hukuk/web-core/api/client";
import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { useErrorMessage } from "@hukuk/web-core/hooks/use-error-message";
import { useTranslations } from "next-intl";
import { useMemo, useState, type FormEvent } from "react";

import { postFeedback } from "@/lib/chat-client";
import type { Answer, FeedbackIn } from "@/lib/chat-types";

const KINDS = ["wrong_source", "wrong_conclusion", "missing", "unclear", "other"] as const;

/** The report form: which point, what kind of error, a comment and what the right answer is (optional). */
export function FeedbackDialog({
    open,
    rating,
    turnId,
    points,
    onClose,
    onSent,
}: {
    open: boolean;
    /** "down" after the thumb, null after "Hata bildir" (a report without a rating). */
    rating: "down" | null;
    turnId: string;
    points: Answer["points"];
    onClose: () => void;
    onSent: () => void;
}) {
    const t = useTranslations("chat.feedback.dialog");
    const kinds = useTranslations("chat.feedback.kinds");
    const errorMessage = useErrorMessage();
    const api = useMemo(() => createApiClient(), []);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (pending) return;
        const form = new FormData(event.currentTarget);
        const point = String(form.get("point"));
        const body: FeedbackIn = {
            rating,
            kind: String(form.get("kind")) as (typeof KINDS)[number],
            point_index: point === "" ? null : Number(point),
            comment: String(form.get("comment") ?? "").trim(),
            correction: String(form.get("correction") ?? "").trim(),
        };
        setPending(true);
        setError(null);
        try {
            await postFeedback(api, turnId, body);
            onSent();
        } catch (failure) {
            setError(errorMessage(failure instanceof ApiFailure ? failure.code : undefined));
        }
        setPending(false);
    }

    return (
        <Dialog open={open} onClose={onClose} title={t("title")} dismissible={!pending}>
            <form onSubmit={submit} className="grid gap-4">
                <div className="grid gap-2">
                    <Label htmlFor="feedback-point">{t("point")}</Label>
                    <Select id="feedback-point" name="point" defaultValue="">
                        <option value="">{t("pointAll")}</option>
                        {points.map((point, index) => (
                            <option key={index} value={index}>
                                {t("pointItem", { index: index + 1, text: point.text })}
                            </option>
                        ))}
                    </Select>
                </div>
                <div className="grid gap-2">
                    <Label htmlFor="feedback-kind">{t("kind")}</Label>
                    <Select id="feedback-kind" name="kind" defaultValue="wrong_conclusion">
                        {KINDS.map((kind) => (
                            <option key={kind} value={kind}>
                                {kinds(kind)}
                            </option>
                        ))}
                    </Select>
                </div>
                <div className="grid gap-2">
                    <Label htmlFor="feedback-comment">{t("comment")}</Label>
                    <Textarea id="feedback-comment" name="comment" rows={3} maxLength={4000} />
                </div>
                <div className="grid gap-2">
                    <Label htmlFor="feedback-correction">{t("correction")}</Label>
                    <Textarea
                        id="feedback-correction"
                        name="correction"
                        rows={3}
                        maxLength={4000}
                    />
                </div>
                <div role="alert">{error ? <p className="text-sm text-low">{error}</p> : null}</div>
                <DialogActions>
                    <Button type="button" variant="outline" onClick={onClose} disabled={pending}>
                        {t("cancel")}
                    </Button>
                    <Button type="submit" disabled={pending}>
                        {t("submit")}
                    </Button>
                </DialogActions>
            </form>
        </Dialog>
    );
}
