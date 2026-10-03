"use client";

import { Input } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useEffectEvent, useState } from "react";

import { useQueueNavigation } from "./use-queue-navigation";

const SEARCH_DEBOUNCE_MS = 300;

/** The `q` box: typing updates the URL after a pause (replace), Enter at once (push). */
export function SearchBox({ id }: { id: string }) {
    const t = useTranslations("review.queue.filters");
    const { params, navigate } = useQueueNavigation();
    const urlValue = params.q ?? "";
    const [text, setText] = useState(urlValue);
    // The last value this box wrote to the URL, and the last URL value seen: a URL change that
    // is not our own (clear filters, back button) replaces the text.
    const [sent, setSent] = useState(urlValue);
    const [seen, setSeen] = useState(urlValue);
    if (urlValue !== seen) {
        setSeen(urlValue);
        if (urlValue !== sent) {
            setText(urlValue);
            setSent(urlValue);
        }
    }

    const sendAfterPause = useEffectEvent((value: string) => {
        setSent(value);
        navigate({ q: value || undefined }, "replace");
    });
    useEffect(() => {
        const value = text.trim();
        if (value === sent) return;
        const timer = setTimeout(() => sendAfterPause(value), SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [text, sent]);

    return (
        <form
            role="search"
            onSubmit={(event) => {
                event.preventDefault();
                const value = text.trim();
                setSent(value);
                navigate({ q: value || undefined });
            }}
        >
            <Input
                id={id}
                type="search"
                value={text}
                maxLength={100}
                placeholder={t("searchPlaceholder")}
                onChange={(event) => setText(event.target.value)}
            />
        </form>
    );
}
