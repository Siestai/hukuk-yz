"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import type { Notice } from "@/lib/queue-params";

/**
 * What the previous review action did, and that the queue is finished. The region is empty on the
 * first paint and gets its text in an effect, so that screen readers announce it. The notice is
 * one-off: once shown it is taken out of the URL (the other params stay), and the server-rendered
 * counts (summary, side-nav badge) are refreshed here, on the screen the action led to.
 */
export function FlashStatus({
    notice,
    atQueue,
    subject = "decision",
}: {
    notice: Notice;
    atQueue: boolean;
    /** What the action was done to: decides the wording of the message. */
    subject?: "decision" | "statute";
}) {
    const t = useTranslations("review.queue");
    const router = useRouter();
    const [text, setText] = useState("");
    const shown = useRef("");
    const flash = notice.flash;
    const finished = atQueue && notice.done;

    useEffect(() => {
        const message = [
            flash ? t(`${subject === "statute" ? "flashStatute" : "flash"}.${flash}`) : null,
            finished ? t("done") : null,
        ]
            .filter(Boolean)
            .join(" ");
        if (!message || shown.current === message) return;
        shown.current = message;
        setText(message);
        const query = new URLSearchParams(window.location.search);
        query.delete("flash");
        query.delete("done");
        const search = query.toString();
        window.history.replaceState(
            null,
            "",
            `${window.location.pathname}${search ? `?${search}` : ""}${window.location.hash}`,
        );
        if (flash) router.refresh();
    }, [flash, finished, router, subject, t]);

    return (
        <div
            role="status"
            className={text ? "rounded-md bg-high-soft p-3 text-sm text-high" : undefined}
        >
            {text}
        </div>
    );
}
