import { useFormatter, useTranslations } from "next-intl";

import type { PendingFiles } from "@/lib/files";

/** The number of files waiting for approval as text: "12", or "100+" when the count stopped at its limit. */
export function usePendingCount() {
    const t = useTranslations("files.list");
    const format = useFormatter();
    return ({ count, more }: PendingFiles) =>
        more ? t("pendingMore", { count }) : format.number(count, "integer");
}
