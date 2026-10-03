"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { SHORTCUT_KEYS, useReviewShortcuts, type Shortcut } from "@/lib/use-review-shortcuts";
import { ActionFailure } from "./action-failure";
import { RejectDialog } from "./reject-dialog";
import { useReviewSession, type Pending } from "./review-session";

function Key({ shortcut }: { shortcut: Shortcut }) {
    return (
        <kbd className="rounded-sm border border-line bg-surface-2 px-1 font-mono text-xs text-ink-2">
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

    useReviewShortcuts(
        {
            approve: () => void session.approve(),
            edit: session.startEdit,
            reject: () => setRejecting(true),
            next: () => void session.move("next"),
            previous: () => void session.move("previous"),
        },
        session.canAct && idle && !rejecting,
    );

    if (!session.canAct) return null;
    const label = (text: string, kind: Pending) => (session.pending === kind ? t("pending") : text);

    return (
        <section
            aria-label={t("label")}
            aria-busy={busy || undefined}
            className="sticky bottom-0 z-10 -mx-8 -mb-8 grid gap-2 border-t border-line bg-surface px-8 py-3"
        >
            {session.failure ? <ActionFailure failure={session.failure} /> : null}
            <div role="status" className="text-sm text-ink-2">
                {session.edge === "next" ? t("noNext") : null}
                {session.edge === "previous" ? t("noPrevious") : null}
            </div>
            <div className="flex flex-wrap items-center gap-3">
                <Button
                    onClick={() => void session.approve()}
                    disabled={!idle}
                    aria-keyshortcuts="A"
                >
                    {label(t("approve"), "approve")} <Key shortcut="approve" />
                </Button>
                <Button
                    variant="outline"
                    onClick={session.startEdit}
                    disabled={!idle}
                    aria-keyshortcuts="E"
                >
                    {label(t("edit"), "edit")} <Key shortcut="edit" />
                </Button>
                <Button
                    variant="destructive"
                    onClick={() => setRejecting(true)}
                    disabled={!idle}
                    aria-keyshortcuts="R"
                >
                    {label(t("reject"), "reject")} <Key shortcut="reject" />
                </Button>
                <p className="ml-auto flex items-center gap-2 text-xs text-ink-3">
                    <span>{t("legend")}</span>
                    <span className="flex items-center gap-1">
                        <Key shortcut="next" /> {t("next")}
                    </span>
                    <span className="flex items-center gap-1">
                        <Key shortcut="previous" /> {t("previous")}
                    </span>
                </p>
            </div>
            <RejectDialog open={rejecting} onClose={() => setRejecting(false)} />
        </section>
    );
}
