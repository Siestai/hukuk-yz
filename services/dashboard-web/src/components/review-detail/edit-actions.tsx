"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { useReviewSession } from "./review-session";

/** The form's id, so the buttons below can submit it from the action bar, away from the form. */
export const EDIT_FORM_ID = "decision-edit-form";

/** Cancel and review of an edit, in the action bar: the form is somewhere up the page, the reviewer is here. */
export function EditActions({ buttonClass }: { buttonClass: string }) {
    const t = useTranslations("review.edit");
    const { busy, cancelEdit } = useReviewSession();
    return (
        <div className="grid grid-cols-2 gap-2 md:flex md:flex-wrap md:items-center md:justify-end md:gap-3">
            <Button
                type="button"
                variant="outline"
                onClick={cancelEdit}
                disabled={busy}
                className={buttonClass}
            >
                {t("cancel")}
            </Button>
            <Button type="submit" form={EDIT_FORM_ID} disabled={busy} className={buttonClass}>
                {t("review")}
            </Button>
        </div>
    );
}
