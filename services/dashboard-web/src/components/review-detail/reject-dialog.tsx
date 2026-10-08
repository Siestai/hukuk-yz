"use client";

import { Dialog } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import type { RefObject } from "react";

import { RejectForm } from "./reject-form";
import { useReviewSession } from "./review-session";

type Props = {
    open: boolean;
    onClose: () => void;
    /** The button that opened it, which gets the focus back whichever way it was opened. */
    returnFocusTo: RefObject<HTMLElement | null>;
};

/** Rejecting needs a reason: the note is required and the button stays off while it is blank. */
export function RejectDialog({ open, onClose, returnFocusTo }: Props) {
    const t = useTranslations("review.reject");
    const session = useReviewSession();
    return (
        <Dialog
            open={open}
            onClose={onClose}
            title={session.subject === "statute" ? t("titleStatute") : t("title")}
            dismissible={!session.busy}
            returnFocusTo={returnFocusTo}
        >
            <RejectForm onClose={onClose} />
        </Dialog>
    );
}
