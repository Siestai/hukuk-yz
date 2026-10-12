import { cn, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { stretchedLink } from "@/components/review-queue/queue-item-parts";
import { fileHref, type FileListItem } from "@/lib/files";
import { useFileFormat } from "./file-format";
import { ReviewBadge } from "./review-badge";
import { ScanBadge } from "./scan-badge";

const cell = "px-2";

/** The file list from `xl`: the resmî sayı sits under the name and the upload under the uploader, so it fits without an inner scroll. */
export function FileTable({ items }: { items: FileListItem[] }) {
    const t = useTranslations("files.list.table");
    const format = useFileFormat();
    const columns = [
        t("name"),
        t("docType"),
        t("docDate"),
        t("uploaded"),
        t("status"),
        t("versions"),
    ];

    return (
        <Table aria-label={t("label")}>
            <TableHeader>
                <TableRow className="hover:bg-surface-2">
                    {columns.map((label) => (
                        <TableHead key={label} className={cell}>
                            {label}
                        </TableHead>
                    ))}
                </TableRow>
            </TableHeader>
            <TableBody>
                {items.map((item) => (
                    <TableRow key={item.id} className="relative">
                        <TableCell className={cn(cell, "min-w-40 max-w-96 py-2")}>
                            <p className="line-clamp-2 font-medium wrap-anywhere text-ink">
                                <Link
                                    href={fileHref(item.id)}
                                    title={format.name(item)}
                                    className={stretchedLink}
                                >
                                    {format.name(item)}
                                </Link>
                            </p>
                            {item.official_ref ? (
                                <p className="font-mono text-xs wrap-anywhere text-ink-2">
                                    {item.official_ref}
                                </p>
                            ) : null}
                        </TableCell>
                        <TableCell className={cell}>{format.docType(item)}</TableCell>
                        <TableCell className={cn(cell, "whitespace-nowrap")}>
                            {format.docDate(item)}
                        </TableCell>
                        <TableCell className={cn(cell, "py-2 text-xs text-ink-2")}>
                            <p>{format.uploader(item)}</p>
                            <p>{format.uploadedAt(item)}</p>
                        </TableCell>
                        <TableCell className={cell}>
                            <div className="flex flex-col items-start gap-1">
                                <ReviewBadge status={item.review_status} />
                                <ScanBadge status={item.scan_status} />
                            </div>
                        </TableCell>
                        <TableCell className={cn(cell, "whitespace-nowrap text-xs text-ink-2")}>
                            {format.versions(item.version_count)}
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );
}
