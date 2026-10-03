import { Skeleton } from "@hukuk/ui";

const ROWS = Array.from({ length: 10 }, (_, i) => i);

/** Stands in for the table while a page of the queue is on its way. */
export function QueueSkeleton() {
    return (
        <div className="grid gap-2">
            {ROWS.map((row) => (
                <Skeleton key={row} className="h-row" />
            ))}
        </div>
    );
}
