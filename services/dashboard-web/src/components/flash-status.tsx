import { useTranslations } from "next-intl";

import type { Notice } from "@/lib/queue-params";

/** What the previous review action did, and that the queue is finished; announced politely, nothing when there is none. */
export function FlashStatus({ notice, atQueue }: { notice: Notice; atQueue: boolean }) {
    const t = useTranslations("review.queue");
    const messages = [
        notice.flash ? t(`flash.${notice.flash}`) : null,
        atQueue && notice.done ? t("done") : null,
    ].filter(Boolean);
    return (
        <div
            role="status"
            className={
                messages.length ? "rounded-md bg-high-soft p-3 text-sm text-high" : undefined
            }
        >
            {messages.join(" ")}
        </div>
    );
}
