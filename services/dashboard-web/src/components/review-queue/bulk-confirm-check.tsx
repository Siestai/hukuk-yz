"use client";

import { Label } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId } from "react";

/** The reviewer takes the records on as their own step; the count is the one they are shown. */
export function BulkConfirmCheck({
    count,
    checked,
    onChange,
}: {
    count: number;
    checked: boolean;
    onChange: (checked: boolean) => void;
}) {
    const t = useTranslations("review.bulk");
    const id = useId();
    return (
        <div className="flex items-start gap-2">
            <input
                id={id}
                type="checkbox"
                checked={checked}
                onChange={(event) => onChange(event.target.checked)}
                className="mt-0.5 size-4 accent-primary"
            />
            <Label htmlFor={id}>{t("check", { count })}</Label>
        </div>
    );
}
