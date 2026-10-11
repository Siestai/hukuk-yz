"use client";

import { Button, Input, Label, Progress, Select, Textarea } from "@hukuk/ui";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useId } from "react";

import { DOC_TYPES, fileHref } from "@/lib/files";
import type { UploadFields } from "@/lib/upload-file";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { UploadFailure } from "./upload-failure";

export type UploadStatus =
    | { kind: "ready" }
    | { kind: "uploading"; fraction: number }
    | { kind: "done"; id: string }
    | { kind: "failed"; code: string | undefined; params: Record<string, unknown> };

export type UploadEntry = {
    key: string;
    file: File;
    fields: UploadFields;
    /** The document type is required (a new file) and was not chosen when the upload was tried. */
    missingType: boolean;
    status: UploadStatus;
};

/** One chosen file: its short form while it waits, then its progress and result. */
export function UploadItem({
    entry,
    typeRequired,
    isAdmin,
    onChange,
    onRemove,
}: {
    entry: UploadEntry;
    typeRequired: boolean;
    isAdmin: boolean;
    onChange: (fields: UploadFields) => void;
    onRemove: () => void;
}) {
    const t = useTranslations("files.upload");
    const format = useFormatter();
    const labels = useEnumLabels();
    const ids = { type: useId(), date: useId(), ref: useId(), url: useId(), note: useId() };
    const { status, fields, file } = entry;
    const editable = status.kind === "ready" || status.kind === "failed";
    const set = (name: keyof UploadFields, value: string) => onChange({ ...fields, [name]: value });

    return (
        <li className="grid gap-3 rounded-md border border-border bg-surface p-4">
            <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 font-medium wrap-anywhere text-ink">{file.name}</p>
                {status.kind !== "uploading" ? (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        aria-label={t("remove", { name: file.name })}
                        onClick={onRemove}
                    >
                        {t("removeShort")}
                    </Button>
                ) : null}
            </div>
            {editable ? (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <div className="grid gap-1.5">
                        <Label htmlFor={ids.type}>
                            {typeRequired ? t("docTypeRequired") : t("docType")}
                        </Label>
                        <Select
                            id={ids.type}
                            value={fields.doc_type ?? ""}
                            aria-invalid={entry.missingType || undefined}
                            aria-describedby={entry.missingType ? `${ids.type}-error` : undefined}
                            onChange={(event) => set("doc_type", event.target.value)}
                        >
                            <option value="">
                                {typeRequired ? t("chooseType") : t("sameAsPrevious")}
                            </option>
                            {DOC_TYPES.map((type) => (
                                <option key={type} value={type}>
                                    {labels.docType(type)}
                                </option>
                            ))}
                        </Select>
                        {entry.missingType ? (
                            <p id={`${ids.type}-error`} className="text-sm text-low">
                                {t("typeMissing")}
                            </p>
                        ) : null}
                    </div>
                    <div className="grid gap-1.5">
                        <Label htmlFor={ids.date}>{t("docDate")}</Label>
                        <Input
                            id={ids.date}
                            type="date"
                            value={fields.doc_date ?? ""}
                            onChange={(event) => set("doc_date", event.target.value)}
                        />
                    </div>
                    <div className="grid gap-1.5">
                        <Label htmlFor={ids.ref}>{t("officialRef")}</Label>
                        <Input
                            id={ids.ref}
                            value={fields.official_ref ?? ""}
                            maxLength={200}
                            onChange={(event) => set("official_ref", event.target.value)}
                        />
                    </div>
                    <div className="grid gap-1.5">
                        <Label htmlFor={ids.url}>{t("originUrl")}</Label>
                        <Input
                            id={ids.url}
                            type="url"
                            inputMode="url"
                            maxLength={2000}
                            value={fields.origin_url ?? ""}
                            onChange={(event) => set("origin_url", event.target.value)}
                        />
                    </div>
                    <div className="grid gap-1.5 md:col-span-2">
                        <Label htmlFor={ids.note}>{t("note")}</Label>
                        <Textarea
                            id={ids.note}
                            value={fields.note ?? ""}
                            maxLength={2000}
                            onChange={(event) => set("note", event.target.value)}
                        />
                    </div>
                </div>
            ) : null}
            {status.kind === "uploading" ? (
                <div className="grid gap-1">
                    <Progress
                        aria-label={t("progress", { name: file.name })}
                        value={Math.round(status.fraction * 100)}
                        max={100}
                    />
                    <p className="font-mono text-xs text-ink-2">
                        {format.number(status.fraction, { style: "percent" })}
                    </p>
                </div>
            ) : null}
            {status.kind === "done" ? (
                <div role="status" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                    <p className="text-high">{t("done")}</p>
                    <Link
                        href={fileHref(status.id)}
                        className="inline-flex items-center font-medium text-primary underline pointer-coarse:min-h-11"
                    >
                        {t("openRecord")}
                    </Link>
                </div>
            ) : null}
            {status.kind === "failed" ? (
                <UploadFailure code={status.code} params={status.params} isAdmin={isAdmin} />
            ) : null}
        </li>
    );
}
