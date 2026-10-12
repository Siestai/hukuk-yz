import Link from "next/link";
import { useTranslations } from "next-intl";

import { stretchedLink } from "@/components/review-queue/queue-item-parts";
import { fileHref, type FileListItem } from "@/lib/files";
import { useFileFormat } from "./file-format";
import { ReviewBadge } from "./review-badge";
import { ScanBadge } from "./scan-badge";

/** The file list below `xl`: the table's files as cards, one link each, fed by the same formatting. */
export function FileCards({ items }: { items: FileListItem[] }) {
    const t = useTranslations("files.list.table");
    const format = useFileFormat();

    return (
        <ul aria-label={t("label")} className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {items.map((item) => (
                <li
                    key={item.id}
                    className="relative grid gap-2 rounded-md border border-border bg-surface p-4 text-sm"
                >
                    <div className="flex items-center justify-between gap-2">
                        <span className="flex flex-wrap items-center gap-1">
                            <ReviewBadge status={item.review_status} />
                            <ScanBadge status={item.scan_status} />
                        </span>
                        <span className="text-xs text-ink-2">
                            {format.versions(item.version_count)}
                        </span>
                    </div>
                    <p className="line-clamp-2 min-w-0 wrap-anywhere font-medium text-ink">
                        <Link
                            href={fileHref(item.id)}
                            title={format.name(item)}
                            className={stretchedLink}
                        >
                            {format.name(item)}
                        </Link>
                    </p>
                    <p className="text-xs text-ink-2">
                        {format.docType(item)}
                        {item.doc_date ? `${format.separator}${format.docDate(item)}` : ""}
                        {item.official_ref ? `${format.separator}${item.official_ref}` : ""}
                    </p>
                    <p className="text-xs text-ink-2">
                        {t("uploadedBy", {
                            name: format.uploader(item),
                            date: format.uploadedAt(item),
                        })}
                    </p>
                </li>
            ))}
        </ul>
    );
}
