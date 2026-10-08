import Link from "next/link";
import { useTranslations } from "next-intl";

import { statuteDetailHref, type StatuteQueueParams } from "@/lib/statute-queue-params";

/** The published text of this article is another extraction's; it links to it. */
export function LiveNotice({ id, queue }: { id: string; queue: StatuteQueueParams }) {
    const t = useTranslations("review.statutes.detail");
    return (
        <section className="grid gap-1 rounded-md border border-border bg-surface-2 p-3 text-sm">
            <p className="text-ink">{t("liveElsewhere")}</p>
            <Link
                href={statuteDetailHref(id, queue)}
                className="inline-flex w-fit items-center font-medium text-primary underline pointer-coarse:min-h-11"
            >
                {t("liveLink")}
            </Link>
        </section>
    );
}
