"use client";

import { Dialog } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { RefObject } from "react";

import { ReopenForm } from "./reopen-form";
import { useReviewSession } from "./review-session";

type Props = {
    open: boolean;
    onClose: () => void;
    /** The button that opened it, which gets the focus back whichever way it was opened. */
    returnFocusTo: RefObject<HTMLElement | null>;
};

/** Says what reopening does and takes an optional note; the form is mounted only while open. */
export function ReopenDialog({ open, onClose, returnFocusTo }: Props) {
    const t = useTranslations("review.reopen");
    const session = useReviewSession();
    return (
        <Dialog
            open={open}
            onClose={onClose}
            title={t("title")}
            dismissible={!session.busy}
            returnFocusTo={returnFocusTo}
        >
            <ReopenForm onClose={onClose} />
        </Dialog>
    );
}
