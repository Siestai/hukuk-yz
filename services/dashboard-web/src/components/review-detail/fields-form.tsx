"use client";

import {
    Button,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    Dialog,
    Input,
    Label,
    Select,
    Textarea,
} from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useState, type FormEvent, type ReactNode } from "react";

import {
    buildEdits,
    initialValues,
    scalarValue,
    type BuiltEdits,
    type EditField,
    type FormValues,
    type ScalarField,
} from "@/lib/decision-edits";
import type { DecisionFields } from "@/lib/decision-fields";
import { useCommon } from "@/lib/use-common";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { failedFields } from "./action-failure";
import { CHOICES } from "./edit-choices";
import { EditSummary } from "./edit-summary";
import { FieldRow } from "./field-row";
import { useReviewSession } from "./review-session";

const NUMBER_INPUTS: ScalarField[] = ["esas_no", "karar_no"];

export function FieldsForm({ fields }: { fields: DecisionFields }) {
    const t = useTranslations();
    const field = (name: string) => t(`fields.${name}`);
    const labels = useEnumLabels();
    const { empty } = useCommon();
    const session = useReviewSession();
    const prefix = useId();
    const [values, setValues] = useState<FormValues>(() => initialValues(fields));
    const [built, setBuilt] = useState<BuiltEdits | null>(null);
    const [confirming, setConfirming] = useState(false);
    const [note, setNote] = useState("");
    const [noChanges, setNoChanges] = useState(false);
    const rejected = new Set<string>(failedFields(session.failure));
    const errors = built?.errors ?? {};
    const hint = (name: EditField) => built?.ignored.includes(name);

    const set = (change: Partial<FormValues>) => {
        setValues((current) => ({ ...current, ...change }));
        setBuilt(null);
        setNoChanges(false);
    };

    /** The message under a field: what the client or the API found wrong, or why an empty value changes nothing. */
    function message(name: EditField): ReactNode {
        const error = errors[name];
        if (error)
            return <span className="text-destructive">{t(`review.edit.errors.${error}`)}</span>;
        if (rejected.has(name)) {
            return <span className="text-destructive">{t("review.edit.errors.server")}</span>;
        }
        if (hint(name)) return <span className="text-ink-3">{t("review.edit.emptyHint")}</span>;
        if (name === "keywords")
            return <span className="text-ink-3">{t("review.edit.listHint")}</span>;
        return null;
    }
    const invalid = (name: EditField) => Boolean(errors[name]) || rejected.has(name);

    function control(name: ScalarField): ReactNode {
        const id = `${prefix}-${name}`;
        const common = {
            id,
            "aria-invalid": invalid(name) || undefined,
            "aria-describedby": `${id}-message`,
        };
        const choice = CHOICES[name];
        const current = values[name];
        if (choice) {
            const label = choice.label(labels);
            const stored = scalarValue(fields, name);
            return (
                <Select
                    {...common}
                    value={current}
                    onChange={(e) => set({ [name]: e.target.value })}
                >
                    {stored === "" ? <option value="">{empty}</option> : null}
                    {stored !== "" && !choice.options.includes(stored) ? (
                        <option value={stored}>{stored}</option>
                    ) : null}
                    {choice.options.map((option) => (
                        <option key={option} value={option}>
                            {label(option)}
                        </option>
                    ))}
                </Select>
            );
        }
        return (
            <Input
                {...common}
                type={name === "decision_date" ? "date" : "text"}
                className={NUMBER_INPUTS.includes(name) ? "font-mono" : undefined}
                value={current}
                onChange={(e) => set({ [name]: e.target.value })}
            />
        );
    }

    function row(name: ScalarField) {
        return (
            <FieldRow key={name} label={<Label htmlFor={`${prefix}-${name}`}>{field(name)}</Label>}>
                {control(name)}
                <p id={`${prefix}-${name}-message`} className="mt-1 text-xs">
                    {message(name)}
                </p>
            </FieldRow>
        );
    }

    function review(event: FormEvent) {
        event.preventDefault();
        const result = buildEdits(fields, values);
        setBuilt(result);
        const changed = Object.keys(result.edits).length > 0;
        setNoChanges(!changed && Object.keys(result.errors).length === 0);
        if (changed && Object.keys(result.errors).length === 0) setConfirming(true);
    }

    async function confirm() {
        if (!built || session.busy) return;
        if (!(await session.submitEdit(built.edits, note))) setConfirming(false);
    }

    const articleErrorId = `${prefix}-related_articles-message`;
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("review.detail.fieldsTitle")}</CardTitle>
            </CardHeader>
            <CardContent>
                <form onSubmit={review} noValidate className="grid gap-4">
                    <dl>
                        {(
                            [
                                "court",
                                "court_level",
                                "chamber",
                                "source_chamber",
                                "bam_region",
                                "decision_kind",
                                "esas_no",
                                "karar_no",
                                "decision_date",
                                "jurisdiction",
                            ] as const
                        ).map(row)}
                        <FieldRow label={field("related_articles")}>
                            <ul className="grid gap-2" aria-describedby={articleErrorId}>
                                {values.related_articles.map((entry, index) => (
                                    <li
                                        key={entry.key}
                                        className="grid grid-cols-4 items-end gap-2"
                                    >
                                        <div className="grid gap-1">
                                            <Label htmlFor={`${prefix}-statute-${entry.key}`}>
                                                {t("review.edit.statute")}
                                            </Label>
                                            <Input
                                                id={`${prefix}-statute-${entry.key}`}
                                                inputMode="numeric"
                                                className="font-mono"
                                                value={entry.statute}
                                                onChange={(e) =>
                                                    set({
                                                        related_articles:
                                                            values.related_articles.map((row) =>
                                                                row.key === entry.key
                                                                    ? {
                                                                          ...row,
                                                                          statute: e.target.value,
                                                                      }
                                                                    : row,
                                                            ),
                                                    })
                                                }
                                            />
                                        </div>
                                        <div className="col-span-2 grid gap-1">
                                            <Label htmlFor={`${prefix}-articles-${entry.key}`}>
                                                {t("review.edit.articles")}
                                            </Label>
                                            <Input
                                                id={`${prefix}-articles-${entry.key}`}
                                                className="font-mono"
                                                value={entry.articles}
                                                onChange={(e) =>
                                                    set({
                                                        related_articles:
                                                            values.related_articles.map((row) =>
                                                                row.key === entry.key
                                                                    ? {
                                                                          ...row,
                                                                          articles: e.target.value,
                                                                      }
                                                                    : row,
                                                            ),
                                                    })
                                                }
                                            />
                                        </div>
                                        <Button
                                            type="button"
                                            variant="ghost"
                                            size="sm"
                                            aria-label={t("review.edit.removeArticle", {
                                                index: index + 1,
                                            })}
                                            onClick={() =>
                                                set({
                                                    related_articles:
                                                        values.related_articles.filter(
                                                            (row) => row.key !== entry.key,
                                                        ),
                                                })
                                            }
                                        >
                                            ×
                                        </Button>
                                    </li>
                                ))}
                            </ul>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                className="mt-2"
                                onClick={() =>
                                    set({
                                        related_articles: [
                                            ...values.related_articles,
                                            {
                                                key:
                                                    Math.max(
                                                        -1,
                                                        ...values.related_articles.map(
                                                            (row) => row.key,
                                                        ),
                                                    ) + 1,
                                                statute: "",
                                                articles: "",
                                                source: null,
                                            },
                                        ],
                                    })
                                }
                            >
                                {t("review.edit.addArticle")}
                            </Button>
                            <p id={articleErrorId} className="mt-1 text-xs">
                                {message("related_articles")}
                            </p>
                        </FieldRow>
                        {row("outcome")}
                        {row("text_completeness")}
                        <FieldRow
                            label={
                                <Label htmlFor={`${prefix}-keywords`}>{field("keywords")}</Label>
                            }
                        >
                            <Textarea
                                id={`${prefix}-keywords`}
                                value={values.keywords}
                                aria-invalid={invalid("keywords") || undefined}
                                aria-describedby={`${prefix}-keywords-message`}
                                onChange={(e) => set({ keywords: e.target.value })}
                            />
                            <p id={`${prefix}-keywords-message`} className="mt-1 text-xs">
                                {message("keywords")}
                            </p>
                        </FieldRow>
                    </dl>
                    {noChanges ? (
                        <p role="status" className="text-sm text-ink-2">
                            {t("review.edit.noChanges")}
                        </p>
                    ) : null}
                    <div className="flex justify-end gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={session.cancelEdit}
                            disabled={session.busy}
                        >
                            {t("review.edit.cancel")}
                        </Button>
                        <Button type="submit" disabled={session.busy}>
                            {t("review.edit.review")}
                        </Button>
                    </div>
                </form>
            </CardContent>
            <Dialog
                open={confirming}
                onClose={() => setConfirming(false)}
                title={t("review.edit.confirm.title")}
            >
                {built ? (
                    <EditSummary fields={fields} edits={built.edits} note={note} onNote={setNote} />
                ) : null}
                <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setConfirming(false)}>
                        {t("review.edit.confirm.cancel")}
                    </Button>
                    <Button type="button" onClick={confirm} disabled={session.busy}>
                        {session.pending === "edit"
                            ? t("review.actions.pending")
                            : t("review.edit.confirm.submit")}
                    </Button>
                </div>
            </Dialog>
        </Card>
    );
}
