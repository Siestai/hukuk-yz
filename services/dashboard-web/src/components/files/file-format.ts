import { useFormatter, useTranslations } from "next-intl";

import { useCommon } from "@/lib/use-common";
import { useDates } from "@/lib/use-dates";
import { useEnumLabels } from "@/lib/use-enum-labels";
import type { FileOut } from "@/lib/files";

const KB = 1024;
const MB = KB * KB;

/**
 * How a file record reads on screen. The table, the cards and the detail page format through
 * this, so a label or a date cannot differ between them.
 */
export function useFileFormat() {
    const t = useTranslations("files.format");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { date, dateTime } = useDates();
    const { empty, separator } = useCommon();

    return {
        empty,
        separator,
        name: (file: FileOut) => file.original_name ?? t("unnamed"),
        docType: (file: FileOut) => (file.doc_type ? labels.docType(file.doc_type) : empty),
        docDate: (file: FileOut) => (file.doc_date ? date(file.doc_date) : empty),
        officialRef: (file: FileOut) => file.official_ref ?? empty,
        uploader: (file: FileOut) => file.uploaded_by_name ?? t("system"),
        uploadedAt: (file: FileOut) => dateTime(file.uploaded_at),
        archivedAt: (file: FileOut) => (file.archived_at ? dateTime(file.archived_at) : empty),
        versions: (count: number) => t("versions", { count }),
        size: (bytes: number) =>
            bytes >= MB
                ? t("sizeMb", { value: format.number(bytes / MB, { maximumFractionDigits: 1 }) })
                : t("sizeKb", { value: format.number(Math.max(1, Math.round(bytes / KB))) }),
    };
}

export type FileFormat = ReturnType<typeof useFileFormat>;
