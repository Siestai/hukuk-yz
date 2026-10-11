import { Badge, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { fileHref, type FileOut } from "@/lib/files";
import { useFileFormat } from "./file-format";
import { ScanBadge } from "./scan-badge";

/** The versions of a document, oldest first; the one on screen is marked, the others link to their record. */
export function VersionHistory({
    versions,
    currentId,
}: {
    versions: FileOut[];
    currentId: string;
}) {
    const t = useTranslations("files.detail.versions");
    const format = useFileFormat();

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent>
                <ol aria-label={t("label")} className="grid grid-cols-1 gap-3">
                    {versions.map((version, index) => (
                        <li
                            key={version.id}
                            className="grid gap-1 rounded-md border border-border p-3 text-sm"
                        >
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium text-ink">
                                    {t("number", { number: index + 1 })}
                                </span>
                                <ScanBadge status={version.scan_status} />
                                {version.id === currentId ? (
                                    <Badge variant="outline">{t("current")}</Badge>
                                ) : null}
                            </div>
                            <p className="wrap-anywhere text-ink">
                                {version.id === currentId ? (
                                    format.name(version)
                                ) : (
                                    <Link
                                        href={fileHref(version.id)}
                                        className="text-primary underline"
                                    >
                                        {format.name(version)}
                                    </Link>
                                )}
                            </p>
                            <p className="text-xs text-ink-2">
                                {t("uploadedBy", {
                                    name: format.uploader(version),
                                    date: format.uploadedAt(version),
                                })}
                            </p>
                        </li>
                    ))}
                </ol>
            </CardContent>
        </Card>
    );
}
