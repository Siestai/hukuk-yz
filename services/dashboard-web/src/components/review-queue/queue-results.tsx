import type { components } from "@/lib/api/schema";
import type { Settled } from "@/lib/api/settle";
import type { QueueParams } from "@/lib/queue-params";
import { QueueCards } from "./queue-cards";
import { CardsHelp } from "./queue-item-parts";
import { QueueEmpty } from "./queue-empty";
import { QueueError } from "./queue-error";
import { QueuePagination } from "./queue-pagination";
import { QueueTable } from "./queue-table";

/**
 * The records with their pagination, or why there are none; waits for the list inside a Suspense
 * boundary. The table (`lg` and up) and the card list (below `lg`: two columns from `md`, one on a phone) are both rendered and CSS shows one:
 * the hidden one leaves the accessibility tree with `display: none`, and the page needs no
 * client-side media query, so the server HTML is right at every width.
 */
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
            <div className="hidden lg:block">
                <QueueTable items={result.data.items} params={params} />
            </div>
            <div className="grid gap-3 lg:hidden">
                <CardsHelp />
                <QueueCards items={result.data.items} params={params} />
            </div>
            <QueuePagination params={params} total={result.data.total} />
        </>
    );
}
