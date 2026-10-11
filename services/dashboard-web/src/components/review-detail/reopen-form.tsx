"use client";

import { Button, DialogActions, Label, Textarea } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { useReviewSession } from "./review-session";

/** The form is mounted only while the dialog is open, so the note starts empty each time. */
export function ReopenForm({ onClose }: { onClose: () => void }) {
    const t = useTranslations("review.reopen");
    const session = useReviewSession();
    const [note, setNote] = useState("");
    const noteId = useId();

    async function submit(event: FormEvent) {
        event.preventDefault();
        if (session.busy) return;
        await session.reopen(note);
        onClose();
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
