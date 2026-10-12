import { Badge } from "@hukuk/ui";

import type { ReviewStatus } from "@/lib/files";
import { useEnumLabels } from "@/lib/use-enum-labels";

const VARIANT = {
    pending: "medium",
    approved: "high",
} as const satisfies Record<ReviewStatus, "medium" | "high">;

export function ReviewBadge({ status }: { status: ReviewStatus }) {
    const labels = useEnumLabels();
    return <Badge variant={VARIANT[status]}>{labels.reviewStatus(status)}</Badge>;
}
