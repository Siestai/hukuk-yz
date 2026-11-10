import { Badge } from "@hukuk/ui";

import type { ScanStatus } from "@/lib/journal-scans";
import { useEnumLabels } from "@/lib/use-enum-labels";

const VARIANT = {
    running: "outline",
    completed: "high",
    completed_with_errors: "medium",
    failed: "low",
} as const satisfies Record<ScanStatus, "outline" | "high" | "medium" | "low">;

export function ScanStatusBadge({ status }: { status: ScanStatus }) {
    const labels = useEnumLabels();
    return <Badge variant={VARIANT[status]}>{labels.journalStatus(status)}</Badge>;
}
