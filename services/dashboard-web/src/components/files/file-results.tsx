import { QueueError } from "@/components/review-queue/queue-error";
import { ACTIVE_SCANS, type FileListParams, type FileListResponse } from "@/lib/files";
import type { Settled } from "@hukuk/web-core/api/settle";
import { FileCards } from "./file-cards";
import { FileEmpty } from "./file-empty";
import { FilePagination } from "./file-pagination";
import { FileTable } from "./file-table";
import { ScanRefresh } from "./scan-refresh";

/**
 * The files of one page with the way to the next, or why there are none; waits for the list inside a
 * Suspense boundary. Table from `xl` and cards below, both rendered and CSS shows one.
 */
export async function FileResults({
    params,
    list,
}: {
    params: FileListParams;
    list: Promise<Settled<FileListResponse>>;
}) {
    const result = await list;
    if (result.error) return <QueueError code={result.error.code} params={result.error.params} />;
    const { items, next_cursor: next } = result.data;
    if (items.length === 0) return <FileEmpty params={params} />;
    return (
        <>
            <ScanRefresh active={items.some((item) => ACTIVE_SCANS.includes(item.scan_status))} />
            <div className="hidden xl:block">
                <FileTable items={items} />
            </div>
            <div className="xl:hidden">
                <FileCards items={items} />
            </div>
            <FilePagination params={params} next={next} />
        </>
    );
}
