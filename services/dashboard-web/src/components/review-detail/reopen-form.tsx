"use client";

import { Button, DialogActions, Label, Textarea } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useId, useState, type FormEvent } from "react";

import { useErrorMessage } from "@/lib/use-error-message";
import { useReviewSession } from "./review-session";

/**
 * The form is mounted only while the dialog is open, so the note starts empty each time. It closes
 * on success and on a conflict (the page shows the record's new state); any other failure keeps
 * the note and is shown here.
 */
export function ReopenForm({ onClose }: { onClose: () => void }) {
    const t = useTranslations("review.reopen");
    const session = useReviewSession();
    const [note, setNote] = useState("");
    const [attempted, setAttempted] = useState(false);
    const message = useErrorMessage();
    const noteId = useId();
    const { failure } = session;
    const conflict =
        attempted && failure?.during === "reopen" && failure.code === "review_conflict";
    const error = attempted && failure?.during === "reopen" && !conflict ? failure : null;

    useEffect(() => {
        if (conflict) onClose();
    }, [conflict, onClose]);

    async function submit(event: FormEvent) {
        event.preventDefault();
        if (session.busy) return;
        setAttempted(true);
        if (await session.reopen(note)) onClose();
    }

    return (
        <form onSubmit={submit} className="grid gap-4">
            <p className="text-sm text-ink-2">{t("intro")}</p>
            <div className="grid gap-1">
                <Label htmlFor={noteId}>{t("note")}</Label>
                <Textarea
                    id={noteId}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                />
            </div>
            {error ? (
                <p role="alert" className="text-sm text-destructive" data-code={error.code}>
                    {message(error.code, error.params)}
                </p>
            ) : null}
            <DialogActions>
                <Button type="button" variant="outline" onClick={onClose} disabled={session.busy}>
                    {t("cancel")}
                </Button>
                <Button type="submit" disabled={session.busy}>
                    {session.pending === "reopen" ? t("pending") : t("submit")}
                </Button>
            </DialogActions>
        </form>
    );
}
