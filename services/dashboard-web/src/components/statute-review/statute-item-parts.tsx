import { Badge } from "@hukuk/ui";

import type { StatuteItem, StatuteItemFormat } from "./statute-item-format";

const STATUS_VARIANT = {
    pending: "outline",
    approved: "high",
    rejected: "low",
    superseded: "medium",
} as const satisfies Record<StatuteItem["status"], "outline" | "high" | "low" | "medium">;

export function StatuteStatusBadge({
    item,
    format,
}: {
    item: StatuteItem;
    format: StatuteItemFormat;
}) {
    return <Badge variant={STATUS_VARIANT[item.status]}>{format.status(item)}</Badge>;
}

export function StatuteBandBadge({
    item,
    format,
}: {
    item: StatuteItem;
    format: StatuteItemFormat;
}) {
    return <Badge variant={item.band}>{format.band(item.band)}</Badge>;
}
