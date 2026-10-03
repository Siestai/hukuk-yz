"use client";

import { Input } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useEffectEvent, useState } from "react";

import { useQueueNavigation } from "./queue-navigation";

const SEARCH_DEBOUNCE_MS = 300;

/** The `q` box: typing updates the URL after a pause (replace), Enter at once (push). */
export function SearchBox({ id }: { id: string }) {
    const t = useTranslations("review.queue.filters");
    const { params, navigate } = useQueueNavigation();
    const urlValue = params.q ?? "";
    const [text, setText] = useState(urlValue);
    // Values this box wrote to the URL that the URL has not shown yet, oldest first, and the last
    // URL value seen. A URL value we sent (or an older one of ours) never replaces the text; any
    // other change (clear filters, back button) does.
    const [sent, setSent] = useState<string[]>([]);
    const [seen, setSeen] = useState(urlValue);
    if (urlValue !== seen) {
        setSeen(urlValue);
        const at = sent.indexOf(urlValue);
        if (at >= 0) {
            setSent(sent.slice(at + 1));
        } else {
            setText(urlValue);
            setSent([]);
        }
    }
    const latest = sent.at(-1) ?? urlValue;

    function send(value: string, mode: "push" | "replace") {
        if (value !== latest) setSent((values) => [...values, value]);
        navigate({ q: value || undefined }, mode);
    }
    const sendAfterPause = useEffectEvent((value: string) => send(value, "replace"));
    useEffect(() => {
        const value = text.trim();
        if (value === latest) return;
        const timer = setTimeout(() => sendAfterPause(value), SEARCH_DEBOUNCE_MS);
        return () => clearTimeout(timer);
    }, [text, latest]);

    return (
        <form
            role="search"
            onSubmit={(event) => {
                event.preventDefault();
                send(text.trim(), "push");
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
