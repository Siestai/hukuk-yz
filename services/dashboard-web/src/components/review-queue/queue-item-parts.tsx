import { Badge, cn } from "@hukuk/ui";
import { useId } from "react";

import { type QueueItem, type QueueItemFormat } from "./queue-item-format";

/** How many reasons a record shows by name; the rest is a count. */
const MAX_REASON_CHIPS = 2;

// The title link of a row or card stretches over it (`after:absolute after:inset-0` on a
// `relative` parent), so the whole record is one click target while keyboard and screen readers
// still get a single link. Tradeoff: text in it cannot be selected with the mouse. Anything else
// interactive inside (a tooltip, a future link or button) needs `relative z-10` to sit above it.
export const stretchedLink = "after:absolute after:inset-0 hover:underline focus-visible:underline";

export function DuplicateIcon({ label }: { label: string }) {
    return (
        <svg
            role="img"
            aria-label={label}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            className="relative z-10 size-4 shrink-0 text-medium"
        >
            <title>{label}</title>
            <rect x={9} y={9} width={11} height={11} rx={2} />
            <path d="M5 15V6a2 2 0 0 1 2-2h9" />
        </svg>
    );
}

/** The band badge with its score. */
export function ConfidenceChip({ item, format }: { item: QueueItem; format: QueueItemFormat }) {
    return (
        <div className="flex items-center gap-2">
            <Badge variant={item.band}>{format.band(item.band)}</Badge>
            <span className="font-mono text-xs text-ink-2">{format.score(item)}</span>
        </div>
    );
}

/** At most two reasons by name and "+N"; the reasons behind the "+N" are read out by screen readers. */
export function ReasonChips({
    item,
    format,
    wrap = false,
}: {
    item: QueueItem;
    format: QueueItemFormat;
    wrap?: boolean;
}) {
    const moreId = useId();
    const rest = item.reasons.slice(MAX_REASON_CHIPS);
    return (
        <ul className={cn("flex gap-1", wrap && "flex-wrap")}>
            {item.reasons.slice(0, MAX_REASON_CHIPS).map((reason) => (
                <li key={reason}>
                    <Badge
                        variant="outline"
                        title={format.isKnownReason(reason) ? undefined : format.unknownReasonLabel}
                    >
                        {format.reason(reason)}
                        {format.isKnownReason(reason) ? null : (
                            <span className="sr-only">{format.unknownReasonLabel}</span>
                        )}
                    </Badge>
                </li>
            ))}
            {rest.length > 0 ? (
                <li>
                    <Badge variant="outline" aria-describedby={moreId}>
                        +{format.count(rest.length)}
                    </Badge>
                    <ul id={moreId} className="sr-only">
                        {rest.map((reason) => (
                            <li key={reason}>{format.reason(reason)}</li>
                        ))}
                    </ul>
                </li>
            ) : null}
        </ul>
    );
}
