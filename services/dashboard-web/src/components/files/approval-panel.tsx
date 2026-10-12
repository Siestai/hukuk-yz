"use client";

import {
    Button,
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    DialogActions,
    Input,
    Select,
    Textarea,
} from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useId, useRef, useState } from "react";

import { createApiClient } from "@/lib/api/client";
import { approveFile } from "@/lib/api/files-client";
import { ApiFailure } from "@/lib/api/review-client";
import { approvalBody, initialValues, type ApprovalValues } from "@/lib/file-approval";
import { readMatches, readSuggestions } from "@/lib/file-suggestions";
import { ACTIVE_SCANS, DOC_TYPES, type FileOut } from "@/lib/files";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { useErrorMessage } from "@/lib/use-error-message";
import { ApprovalField } from "./approval-field";
import { ApprovalMatches } from "./approval-matches";
import { DeleteFileDialog } from "./delete-file-dialog";

/**
 * The approval screen of a pending file, at the top of its detail: every field starts with the
 * suggested value (editable) and says where it came from; the match box offers the version link.
 * "Onayla" needs a document type; "Sil" asks first. While the scan runs there are no suggestions
 * yet, so the form waits for it.
 */
export function ApprovalPanel({
    file,
    names,
    canDelete,
}: {
    file: FileOut;
    /** Names of the files in `file.matches`, by id. */
    names: Record<string, string>;
    canDelete: boolean;
}) {
    const t = useTranslations("files.detail.approve");
    const labels = useEnumLabels();
    const errorMessage = useErrorMessage();
    const router = useRouter();
    const suggestions = readSuggestions(file.suggestions);
    const matches = readMatches(file.matches);
    const [values, setValues] = useState<ApprovalValues>(() => initialValues(file, suggestions));
    const [linked, setLinked] = useState(false);
    const [busy, setBusy] = useState(false);
    const [failure, setFailure] = useState<string>();
    const [deleting, setDeleting] = useState(false);
    const deleteButton = useRef<HTMLButtonElement>(null);
    const ids = {
        type: useId(),
        date: useId(),
        ref: useId(),
        title: useId(),
        url: useId(),
        note: useId(),
        heading: useId(),
    };
    const set = (name: keyof ApprovalValues, value: string) =>
        setValues((current) => ({ ...current, [name]: value }));

    const body = approvalBody(
        values,
        matches.previous ? { previousId: matches.previous.fileId, linked } : null,
    );

    async function approve() {
        if (!body) return;
        setBusy(true);
        setFailure(undefined);
        try {
            await approveFile(createApiClient(), file.id, body);
            router.refresh();
        } catch (error) {
            const code = error instanceof ApiFailure ? error.code : undefined;
            setFailure(errorMessage(code));
            // Someone approved it first: the page shows the file as it is now.
            if (code === "file_not_pending") router.refresh();
        } finally {
            setBusy(false);
        }
    }

    const scanning = ACTIVE_SCANS.includes(file.scan_status);

    return (
        <Card role="region" aria-labelledby={ids.heading}>
            <CardHeader>
                <CardTitle id={ids.heading}>{t("title")}</CardTitle>
                <p className="text-sm text-ink-2">{scanning ? t("scanning") : t("intro")}</p>
            </CardHeader>
            {scanning ? null : (
                <CardContent className="grid gap-4">
                    {Object.keys(suggestions).length === 0 ? (
                        <p className="text-sm text-ink-2">{t("noSuggestions")}</p>
                    ) : null}
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                        <ApprovalField
                            id={ids.type}
                            label={t("docType")}
                            field="doc_type"
                            suggestion={suggestions.doc_type}
                            value={values.doc_type}
                        >
                            <Select
                                id={ids.type}
                                value={values.doc_type}
                                onChange={(event) => set("doc_type", event.target.value)}
                            >
                                <option value="">{t("chooseType")}</option>
                                {DOC_TYPES.map((type) => (
                                    <option key={type} value={type}>
                                        {labels.docType(type)}
                                    </option>
                                ))}
                            </Select>
                        </ApprovalField>
                        <ApprovalField
                            id={ids.date}
                            label={t("docDate")}
                            field="doc_date"
                            suggestion={suggestions.doc_date}
                            value={values.doc_date}
                        >
                            <Input
                                id={ids.date}
                                type="date"
                                value={values.doc_date}
                                onChange={(event) => set("doc_date", event.target.value)}
                            />
                        </ApprovalField>
                        <ApprovalField
                            id={ids.ref}
                            label={t("officialRef")}
                            field="official_ref"
                            suggestion={suggestions.official_ref}
                            value={values.official_ref}
                        >
                            <Input
                                id={ids.ref}
                                value={values.official_ref}
                                maxLength={200}
                                onChange={(event) => set("official_ref", event.target.value)}
                            />
                        </ApprovalField>
                        <ApprovalField
                            id={ids.title}
                            label={t("titleField")}
                            field="title"
                            suggestion={suggestions.title}
                            value={values.title}
                        >
                            <Input
                                id={ids.title}
                                value={values.title}
                                maxLength={500}
                                onChange={(event) => set("title", event.target.value)}
                            />
                        </ApprovalField>
                        <ApprovalField
                            id={ids.url}
                            label={t("originUrl")}
                            value={values.origin_url}
                        >
                            <Input
                                id={ids.url}
                                type="url"
                                inputMode="url"
                                maxLength={2000}
                                value={values.origin_url}
                                onChange={(event) => set("origin_url", event.target.value)}
                            />
                        </ApprovalField>
                        <ApprovalField
                            id={ids.note}
                            label={t("note")}
                            value={values.note}
                            className="md:col-span-2"
                        >
                            <Textarea
                                id={ids.note}
                                maxLength={2000}
                                value={values.note}
                                onChange={(event) => set("note", event.target.value)}
                            />
                        </ApprovalField>
                    </div>
                    <ApprovalMatches
                        matches={matches}
                        names={names}
                        linked={linked}
                        onLinkedChange={setLinked}
                    />
                    {failure ? (
                        <p role="alert" className="text-sm text-low">
                            {failure}
                        </p>
                    ) : null}
                    <DialogActions>
                        {canDelete ? (
                            <Button
                                ref={deleteButton}
                                type="button"
                                variant="outline"
                                disabled={busy}
                                onClick={() => setDeleting(true)}
                            >
                                {t("delete")}
                            </Button>
                        ) : null}
                        <Button
                            type="button"
                            disabled={!body || busy}
                            onClick={() => void approve()}
                        >
                            {busy ? t("approving") : t("approve")}
                        </Button>
                    </DialogActions>
                    <DeleteFileDialog
                        open={deleting}
                        onClose={() => setDeleting(false)}
                        fileId={file.id}
                        name={file.original_name ?? t("matches.unnamed")}
                        returnFocusTo={deleteButton}
                    />
                </CardContent>
            )}
        </Card>
    );
}
