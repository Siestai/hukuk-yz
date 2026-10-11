import Link from "next/link";
import { useTranslations } from "next-intl";

import { fileListHref, type FileListParams } from "@/lib/files";

const linkClass =
    "inline-flex items-center text-sm font-medium text-primary underline pointer-coarse:min-h-11";

/** The list is paged by cursor: only the way on and the way back to the first page are known. */
export function FilePagination({ params, next }: { params: FileListParams; next: string | null }) {
    const t = useTranslations("files.list.pagination");
    if (!params.cursor && !next) return null;
    return (
        <nav aria-label={t("label")} className="mt-4 flex items-center justify-between gap-4">
            {params.cursor ? (
                <Link href={fileListHref({ ...params, cursor: undefined })} className={linkClass}>
                    {t("first")}
                </Link>
            ) : (
                <span />
            )}
            {next ? (
                <Link href={fileListHref({ ...params, cursor: next })} className={linkClass}>
                    {t("next")}
                </Link>
            ) : null}
        </nav>
    );
}
