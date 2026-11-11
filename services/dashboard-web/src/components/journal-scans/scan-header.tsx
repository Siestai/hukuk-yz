import Link from "next/link";
import { useTranslations } from "next-intl";

import type { JournalScanItem } from "@/lib/journal-scans";
import { useScanFormat } from "./scan-format";
import { ScanStatusBadge } from "./scan-status-badge";

export function ScanHeader({ scan }: { scan: JournalScanItem }) {
    const t = useTranslations("journalScans.detail");
    const format = useScanFormat();
    return (
        <header className="grid gap-3">
            <Link
                href="/taramalar"
                className="inline-flex w-fit items-center text-sm text-primary hover:underline pointer-coarse:min-h-11"
            >
                {t("back")}
            </Link>
            <h1 className="font-serif text-xl wrap-anywhere text-ink md:text-2xl">
                {t("title", { date: format.startedAt(scan) })}
            </h1>
            <div className="flex flex-wrap items-center gap-2 text-sm text-ink-2">
                <ScanStatusBadge status={scan.status} />
                {format.trigger(scan)}
            </div>
        </header>
    );
}
