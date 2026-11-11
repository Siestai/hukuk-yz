import { Card, CardContent } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";

import { QueueError } from "@/components/review-queue/queue-error";
import { scanListHref, type JournalScanList } from "@/lib/journal-scans";
import type { Settled } from "@hukuk/web-core/api/settle";
import { ScanCards } from "./scan-cards";
import { ScanPagination } from "./scan-pagination";
import { ScanTable } from "./scan-table";

function ScanEmpty({ page }: { page: number }) {
    const t = useTranslations("journalScans.list.empty");
    return (
        <Card>
            <CardContent className="grid justify-items-center gap-3 p-10 text-center">
                <p className="text-ink">{page > 1 ? t("pastEnd") : t("none")}</p>
                {page > 1 ? (
                    <Link
                        href={scanListHref(1)}
                        className="inline-flex items-center text-sm font-medium text-primary underline pointer-coarse:min-h-11"
                    >
                        {t("first")}
                    </Link>
                ) : null}
            </CardContent>
        </Card>
    );
}

/** One page of scans, or why there are none; waits for the list inside a Suspense boundary. */
export async function ScanResults({
    page,
    list,
}: {
    page: number;
    list: Promise<Settled<JournalScanList>>;
}) {
    const result = await list;
    if (result.error) return <QueueError code={result.error.code} params={result.error.params} />;
    const { items, total } = result.data;
    if (items.length === 0) return <ScanEmpty page={page} />;
    return (
        <>
            <div className="hidden xl:block">
                <ScanTable items={items} />
            </div>
            <div className="xl:hidden">
                <ScanCards items={items} />
            </div>
            <ScanPagination page={page} total={total} />
        </>
    );
}
