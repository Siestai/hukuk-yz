import { Card, CardContent } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { activeFileFilters, fileListHref, type FileListParams } from "@/lib/files";

const linkClass =
    "inline-flex items-center text-sm font-medium text-primary underline pointer-coarse:min-h-11";

/** Nothing to show: no file yet, the filters match nothing, or the page is past the last. */
export function FileEmpty({ params }: { params: FileListParams }) {
    const t = useTranslations("files.list");
    return (
        <Card>
            <CardContent className="grid justify-items-center gap-3 p-10 text-center">
                {params.cursor ? (
                    <>
                        <p className="text-ink">{t("empty.pastEnd")}</p>
                        <Link
                            href={fileListHref({ ...params, cursor: undefined })}
                            className={linkClass}
                        >
                            {t("pagination.first")}
                        </Link>
                    </>
                ) : activeFileFilters(params) > 0 ? (
                    <>
                        <p className="text-ink">{t("empty.filtered")}</p>
                        <Link href={fileListHref({})} className={linkClass}>
                            {t("empty.clear")}
                        </Link>
                    </>
                ) : (
                    <p className="text-ink">{t("empty.none")}</p>
                )}
            </CardContent>
        </Card>
    );
}
