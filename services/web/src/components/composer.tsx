"use client";

import { Button, Textarea } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState, type FormEvent, type KeyboardEvent } from "react";

/** The question box at the bottom. Enter sends, Shift+Enter starts a new line. */
export function Composer({
    disabled,
    onSend,
}: {
    disabled: boolean;
    onSend: (text: string) => void;
}) {
    const t = useTranslations("chat.composer");
    const [text, setText] = useState("");

    function send(event?: FormEvent) {
        event?.preventDefault();
        const trimmed = text.trim();
        if (!trimmed || disabled) return;
        setText("");
        onSend(trimmed);
    }

    function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault();
            send();
        }
    }

    return (
        <form
            onSubmit={send}
            className="flex items-end gap-2 border-t border-line bg-surface px-safe-4 pt-3 pb-safe-3 md:px-safe-6"
        >
            <Textarea
                value={text}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={onKeyDown}
                aria-label={t("label")}
                placeholder={t("placeholder")}
                rows={1}
                maxLength={4000}
                className="max-h-40 min-h-11 flex-1 resize-none"
            />
            <Button type="submit" size="lg" disabled={disabled || !text.trim()}>
                {t("send")}
            </Button>
        </form>
    );
}
