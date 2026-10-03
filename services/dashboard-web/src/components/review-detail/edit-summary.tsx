"use client";

import { Label, Textarea } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId } from "react";

import {
    EDIT_FIELDS,
    scalarValue,
    type BuiltEdits,
    type EditField,
    type ScalarField,
} from "@/lib/decision-edits";
import type { DecisionFields } from "@/lib/decision-fields";
import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { CHOICES } from "./edit-choices";
import { articleText } from "./fields-card";

/** What the confirm dialog shows: each changed field as "label: old → new", and the optional note. */
export function EditSummary({
    fields,
    edits,
    note,
    onNote,
}: {
    fields: DecisionFields;
    edits: BuiltEdits["edits"];
    note: string;
    onNote: (note: string) => void;
}) {
    const t = useTranslations();
    const labels = useEnumLabels();
    const { date } = useDates();
    const { empty } = useCommon();
    const noteId = useId();

    function show(name: EditField, source: Record<string, unknown>): string {
        const value = source[name];
        if (name === "keywords")
            return Array.isArray(value) && value.length ? value.join(", ") : empty;
        if (name === "related_articles") {
            return Array.isArray(value) && value.length
                ? value.map((entry) => articleText(entry, t)).join("; ")
                : empty;
        }
        const text = typeof value === "string" ? value : "";
        if (!text) return empty;
        const choice = CHOICES[name as ScalarField];
        if (choice) return choice.label(labels)(text);
        return name === "decision_date" ? date(text) : text;
    }

    const before: Record<string, unknown> = Object.fromEntries(
        EDIT_FIELDS.map((name) => [
            name,
            name === "keywords"
                ? fields.keywords
                : name === "related_articles"
                  ? fields.relatedArticles
                  : scalarValue(fields, name),
        ]),
    );

    return (
        <>
            <p className="text-sm text-ink-2">{t("review.edit.confirm.intro")}</p>
            <ul className="grid gap-1 text-sm">
                {EDIT_FIELDS.filter((name) => name in edits).map((name) => (
                    <li key={name} className="wrap-anywhere text-ink">
                        {t("review.edit.confirm.change", {
                            field: t(`fields.${name}`),
                            before: show(name, before),
                            after: show(name, edits),
                        })}
                    </li>
                ))}
            </ul>
            <div className="grid gap-1">
                <Label htmlFor={noteId}>{t("review.edit.confirm.note")}</Label>
                <Textarea
                    id={noteId}
                    value={note}
                    onChange={(event) => onNote(event.target.value)}
                />
            </div>
        </>
    );
}
