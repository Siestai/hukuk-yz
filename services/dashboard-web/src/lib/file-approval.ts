import type { FileApproval } from "@/lib/api/files-client";
import type { Suggestions } from "@/lib/file-suggestions";
import { DOC_TYPES, type FileOut } from "@/lib/files";

export const APPROVAL_FIELDS = [
    "doc_type",
    "doc_date",
    "official_ref",
    "title",
    "origin_url",
    "note",
] as const;
export type ApprovalValues = Record<(typeof APPROVAL_FIELDS)[number], string>;

/** What the form starts with: the suggested value of a field, else what the record already holds. */
export function initialValues(file: FileOut, suggestions: Suggestions): ApprovalValues {
    return {
        doc_type: suggestions.doc_type?.value ?? file.doc_type ?? "",
        doc_date: suggestions.doc_date?.value ?? file.doc_date ?? "",
        official_ref: suggestions.official_ref?.value ?? file.official_ref ?? "",
        title: suggestions.title?.value ?? file.title ?? "",
        origin_url: file.origin_url ?? "",
        note: file.note ?? "",
    };
}

/**
 * The approval request for the form, or null while no known document type is chosen. A blank
 * field is sent as empty (the API writes what it is sent). `link` is the version decision when the
 * file was offered as the next version of another: the id links it, null keeps it a document of
 * its own; without a decision `supersedes_id` is left out and the upload's own link stays.
 */
export function approvalBody(
    values: ApprovalValues,
    link: { previousId: string; linked: boolean } | null,
): FileApproval | null {
    const docType = DOC_TYPES.find((type) => type === values.doc_type);
    if (!docType) return null;
    return {
        doc_type: docType,
        doc_date: values.doc_date || null,
        official_ref: values.official_ref || null,
        title: values.title || null,
        origin_url: values.origin_url || null,
        note: values.note || null,
        ...(link ? { supersedes_id: link.linked ? link.previousId : null } : {}),
    };
}
