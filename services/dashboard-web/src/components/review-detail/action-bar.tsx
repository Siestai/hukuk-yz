"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { SHORTCUT_KEYS, useReviewShortcuts, type Shortcut } from "@/lib/use-review-shortcuts";
import { ActionFailure } from "./action-failure";
import { RejectDialog } from "./reject-dialog";
import { useReviewSession, type Pending } from "./review-session";

// On a phone the three buttons share one row, so a long label wraps instead of widening its button.
const actionButton =
    "h-auto min-h-9 whitespace-normal leading-tight pointer-coarse:h-auto pointer-coarse:min-h-11 md:whitespace-nowrap";

function Key({ shortcut }: { shortcut: Shortcut }) {
    return (
        <kbd className="hidden rounded-sm border border-line bg-surface-2 px-1 font-mono text-xs text-ink-2 md:inline">
            {SHORTCUT_KEYS[shortcut]}
        </kbd>
    );
}

/**
 * Approve, edit and reject of the record, with their keyboard shortcuts and the move to the
 * next or previous record. Renders nothing for a record that is not in the queue.
 */
export function ActionBar() {
    const t = useTranslations("review.actions");
    const session = useReviewSession();
    const [rejecting, setRejecting] = useState(false);
    const { busy, mode } = session;
    const idle = !busy && mode === "view";
    const editButton = useRef<HTMLButtonElement>(null);
    const rejectButton = useRef<HTMLButtonElement>(null);
    const wasEditing = useRef(false);

    // The form of an edit is gone when it is cancelled: the focus goes back to the button that opened it.
    useEffect(() => {
        if (wasEditing.current && mode === "view") editButton.current?.focus();
        wasEditing.current = mode === "edit";
    }, [mode]);

    useReviewShortcuts(
        {
            approve: () => void session.approve(),
            edit: session.startEdit,
            reject: () => session.canAct && setRejecting(true),
            next: () => void session.move("next"),
            previous: () => void session.move("previous"),
        },
        idle && !rejecting,
    );

    if (!session.canAct) return null;
    const label = (text: string, kind: Pending) => (session.pending === kind ? t("pending") : text);

    return (
        <section
            aria-label={t("label")}
            aria-busy={busy || undefined}
            className="sticky bottom-0 z-10 -mx-4 -mb-4 flex max-h-56 flex-col gap-2 md:max-h-none border-t border-line bg-surface px-4 pt-3 pb-safe-3 md:-mx-6 md:-mb-6 md:px-6 lg:-mx-8 lg:-mb-8 lg:px-8"
        >
            {session.failure ? (
                <div className="min-h-0 overflow-y-auto">
                    <ActionFailure failure={session.failure} />
                </div>
            ) : null}
            <div role="status" className="text-sm text-ink-2">
                {session.edge === "next" ? t("noNext") : null}
                {session.edge === "previous" ? t("noPrevious") : null}
            </div>
            <div className="grid grid-cols-3 gap-2 md:flex md:flex-wrap md:items-center md:gap-3">
                <Button
                    onClick={() => void session.approve()}
                    disabled={!idle}
                    aria-keyshortcuts="A"
                    className={actionButton}
                >
                    {label(t("approve"), "approve")} <Key shortcut="approve" />
                </Button>
                <Button
                    ref={editButton}
                    variant="outline"
                    onClick={session.startEdit}
                    disabled={!idle}
                    aria-keyshortcuts="E"
                    className={actionButton}
                >
                    {label(t("edit"), "edit")} <Key shortcut="edit" />
                </Button>
                <Button
                    ref={rejectButton}
                    variant="destructive"
                    onClick={() => setRejecting(true)}
                    disabled={!idle}
                    aria-keyshortcuts="R"
                    className={actionButton}
                >
                    {label(t("reject"), "reject")} <Key shortcut="reject" />
                </Button>
                <p className="ml-auto hidden items-center gap-2 text-xs text-ink-3 md:flex">
                    <span>{t("legend")}</span>
                    <span className="flex items-center gap-1">
                        <Key shortcut="next" /> {t("next")}
                    </span>
                    <span className="flex items-center gap-1">
                        <Key shortcut="previous" /> {t("previous")}
                    </span>
                </p>
            </div>
            <RejectDialog
                open={rejecting}
                onClose={() => setRejecting(false)}
                returnFocusTo={rejectButton}
            />
        </section>
    );
}
