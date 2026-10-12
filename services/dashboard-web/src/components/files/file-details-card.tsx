import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { webLink, type FileOut } from "@/lib/files";
import { useFileFormat } from "./file-format";

/** The record's own fields, as stored. */
export function FileDetailsCard({ file }: { file: FileOut }) {
    const t = useTranslations("files.detail.fields");
    const format = useFileFormat();
    const link = webLink(file.origin_url);
    const rows: { label: string; value: string; mono?: boolean }[] = [
        { label: t("docType"), value: format.docType(file) },
        { label: t("titleField"), value: file.title ?? format.empty },
        { label: t("docDate"), value: format.docDate(file) },
        { label: t("officialRef"), value: format.officialRef(file), mono: true },
        { label: t("note"), value: file.note ?? format.empty },
        { label: t("size"), value: format.size(file.size) },
        { label: t("uploader"), value: format.uploader(file) },
        { label: t("uploadedAt"), value: format.uploadedAt(file) },
        { label: t("sha256"), value: file.sha256, mono: true },
        ...(file.archived_at ? [{ label: t("archivedAt"), value: format.archivedAt(file) }] : []),
    ];

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent>
                <dl className="grid grid-cols-1 gap-3 text-sm">
                    {rows.map(({ label, value, mono }) => (
                        <div key={label} className="grid gap-0.5">
                            <dt className="text-xs text-ink-2">{label}</dt>
                            <dd
                                className={
                                    mono ? "font-mono text-xs wrap-anywhere" : "wrap-anywhere"
                                }
                            >
                                {value}
                            </dd>
                        </div>
                    ))}
                    <div className="grid gap-0.5">
                        <dt className="text-xs text-ink-2">{t("originUrl")}</dt>
                        <dd className="wrap-anywhere">
                            {link ? (
                                <a
                                    href={link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-primary underline"
                                >
                                    {file.origin_url}
                                </a>
                            ) : (
                                (file.origin_url ?? format.empty)
                            )}
                        </dd>
                    </div>
                </dl>
            </CardContent>
        </Card>
    );
}
