"use client";

import { Button, DialogActions, Label, Textarea } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent } from "react";

import { useReviewSession } from "./review-session";

/** The form is mounted only while the dialog is open, so the note and its error start fresh each time. */
export function RejectForm({ onClose }: { onClose: () => void }) {
    const t = useTranslations("review.reject");
    const session = useReviewSession();
    const [note, setNote] = useState("");
    const [submitted, setSubmitted] = useState(false);
    const noteId = useId();
    const blank = note.trim() === "";

    async function submit(event: FormEvent) {
        event.preventDefault();
        setSubmitted(true);
        if (blank || session.busy) return;
        if (!(await session.reject(note))) onClose();
    }

    return (
        <form onSubmit={submit} className="grid gap-4" noValidate>
            <p className="text-sm text-ink-2">
                {session.subject === "statute" ? t("introStatute") : t("intro")}
            </p>
            <div className="grid gap-1">
                <Label htmlFor={noteId}>{t("note")}</Label>
                <Textarea
                    id={noteId}
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                    aria-invalid={submitted && blank}
                    aria-describedby={submitted && blank ? `${noteId}-error` : undefined}
                />
                {submitted && blank ? (
                    <p id={`${noteId}-error`} className="text-sm text-destructive">
                        {t("required")}
                    </p>
                ) : null}
            </div>
            <DialogActions>
                <Button type="button" variant="outline" onClick={onClose} disabled={session.busy}>
                    {t("cancel")}
                </Button>
                <Button type="submit" variant="destructive" disabled={blank || session.busy}>
                    {t("submit")}
                </Button>
            </DialogActions>
        </form>
    );
}
