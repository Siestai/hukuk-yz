import type { components } from "@/lib/api/schema";
import type { Settled } from "@/lib/api/settle";
import type { QueueParams } from "@/lib/queue-params";
import { BulkApproveButton } from "./bulk-approve-button";

/** How many records the dialog shows as examples. */
const SAMPLE_SIZE = 5;

/**
 * The bulk approve button with the list it will confirm: the total and the first records of the
 * list response on screen. Without the list (still loading, or failed) the button is shown shut.
 */
export async function QueueBulkApprove({
    params,
    list,
}: {
    params: QueueParams;
    list?: Promise<Settled<components["schemas"]["ReviewListResponse"]>>;
}) {
    const result = list ? await list : undefined;
    const data = result?.data;
    return (
        <BulkApproveButton
            params={params}
            unavailable={!data}
            total={data?.total ?? 0}
            sample={(data?.items ?? []).slice(0, SAMPLE_SIZE).map((item) => ({
                id: item.extraction_id,
                title: item.title,
                esasNo: item.esas_no,
                kararNo: item.karar_no,
            }))}
        />
    );
}
