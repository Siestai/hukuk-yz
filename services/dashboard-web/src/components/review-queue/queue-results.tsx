import type { components } from "@/lib/api/schema";
import type { Settled } from "@/lib/api/settle";
import type { QueueParams } from "@/lib/queue-params";
import { QueueEmpty } from "./queue-empty";
import { QueueError } from "./queue-error";
import { QueuePagination } from "./queue-pagination";
import { QueueTable } from "./queue-table";

/** The table with its pagination, or why there is none; waits for the list inside a Suspense boundary. */
export async function QueueResults({
    params,
    list,
}: {
    params: QueueParams;
    list: Promise<Settled<components["schemas"]["ReviewListResponse"]>>;
}) {
    const result = await list;
    if (result.error) return <QueueError code={result.error.code} params={result.error.params} />;
    if (result.data.items.length === 0) {
        return <QueueEmpty params={params} pastEnd={result.data.total > 0} />;
    }
    return (
        <>
            <QueueTable items={result.data.items} params={params} />
            <QueuePagination params={params} total={result.data.total} />
        </>
    );
}
