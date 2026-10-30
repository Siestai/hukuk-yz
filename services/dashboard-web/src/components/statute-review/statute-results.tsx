import { QueueError } from "@/components/review-queue/queue-error";
import { CardsHelp } from "@/components/review-queue/queue-item-parts";
import { QueuePagination } from "@/components/review-queue/queue-pagination";
import type { components } from "@hukuk/web-core/api/schema";
import type { Settled } from "@hukuk/web-core/api/settle";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { StatuteCards } from "./statute-cards";
import { StatuteEmpty } from "./statute-empty";
import { StatuteTable } from "./statute-table";

/**
 * The articles with their pagination, or why there are none; waits for the list inside a Suspense
 * boundary. Table from `xl` and cards below, both rendered and CSS shows one (as for decisions).
 */
export async function StatuteResults({
    params,
    list,
}: {
    params: StatuteQueueParams;
    list: Promise<Settled<components["schemas"]["StatuteReviewListResponse"]>>;
}) {
    const result = await list;
    if (result.error) return <QueueError code={result.error.code} params={result.error.params} />;
    if (result.data.items.length === 0) {
        return <StatuteEmpty params={params} pastEnd={result.data.total > 0} />;
    }
    return (
        <>
            <div className="hidden xl:block">
                <StatuteTable items={result.data.items} params={params} />
            </div>
            <div className="grid gap-3 xl:hidden">
                <CardsHelp scope="statutes" />
                <StatuteCards items={result.data.items} params={params} />
            </div>
            <QueuePagination params={params} total={result.data.total} />
        </>
    );
}
