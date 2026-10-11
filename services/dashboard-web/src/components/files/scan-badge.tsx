import { Badge } from "@hukuk/ui";

import type { ScanStatus } from "@/lib/files";
import { useEnumLabels } from "@/lib/use-enum-labels";

const VARIANT = {
    queued: "outline",
    running: "default",
    done: "high",
    needs_ocr: "medium",
    unsupported: "medium",
    failed: "low",
} as const satisfies Record<ScanStatus, "default" | "outline" | "high" | "medium" | "low">;

export function ScanBadge({ status }: { status: ScanStatus }) {
    const labels = useEnumLabels();
    return <Badge variant={VARIANT[status]}>{labels.scanStatus(status)}</Badge>;
}
