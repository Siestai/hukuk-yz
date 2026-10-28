"use client";

import { Button, Card, Input } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import type { CaseFacts, Fact } from "@/lib/chat-types";

/**
 * "Anladığım olay": what the agent understood. Unknown values stand out; on the latest turn a
 * value can be tapped and corrected, and the correction goes out as a new message.
 */
export function FactsCard({
    facts,
    onCorrect,
    focusKey,
}: {
    facts: CaseFacts;
    /** Absent: the card is read-only (an older turn). */
    onCorrect?: (message: string) => void;
    /** The fact whose editor opens first. */
    focusKey?: string;
}) {
    const t = useTranslations("chat.facts");
    const [editing, setEditing] = useState<string | null>(focusKey ?? null);

    function submit(event: FormEvent<HTMLFormElement>, fact: Fact) {
        event.preventDefault();
        const value = String(new FormData(event.currentTarget).get("value") ?? "").trim();
        if (!value) return;
        setEditing(null);
        onCorrect?.(t("correction", { label: fact.label, value }));
    }

    return (
        <Card className="p-4">
            <h3 className="text-sm font-semibold text-ink-2">{t("title")}</h3>
            <dl className="mt-2 grid grid-cols-1 divide-y divide-line-2">
                {facts.facts.map((fact) => (
                    <div
                        key={fact.key}
                        className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-2"
                    >
                        <dt className="text-sm text-ink-2">{fact.label}</dt>
                        <dd className="min-w-0">
                            {editing === fact.key ? (
                                <form
                                    onSubmit={(event) => submit(event, fact)}
                                    className="flex items-center gap-2"
                                >
                                    <Input
                                        name="value"
                                        defaultValue={fact.value ?? ""}
                                        aria-label={t("editValue", { label: fact.label })}
                                        autoFocus
                                    />
                                    <Button type="submit" size="sm">
                                        {t("save")}
                                    </Button>
                                    <Button
                                        type="button"
                                        size="sm"
                                        variant="ghost"
                                        onClick={() => setEditing(null)}
                                    >
                                        {t("cancel")}
                                    </Button>
                                </form>
                            ) : (
                                <FactValue
                                    fact={fact}
                                    unknownText={t("unknown")}
                                    editLabel={t("editValue", { label: fact.label })}
                                    onEdit={onCorrect ? () => setEditing(fact.key) : undefined}
                                />
                            )}
                        </dd>
                    </div>
                ))}
            </dl>
        </Card>
    );
}

function FactValue({
    fact,
    unknownText,
    editLabel,
    onEdit,
}: {
    fact: Fact;
    unknownText: string;
    editLabel: string;
    onEdit?: () => void;
}) {
    const unknown = fact.status === "unknown";
    const className = unknown ? "font-medium text-medium" : "font-medium text-ink";
    const text = unknown ? unknownText : fact.value;
    if (!onEdit) return <span className={`${className} wrap-anywhere text-sm`}>{text}</span>;
    return (
        <button
            type="button"
            onClick={onEdit}
            aria-label={`${editLabel}: ${text}`}
            className={`${className} wrap-anywhere min-h-8 text-right text-sm focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:min-h-11`}
        >
            {text}
        </button>
    );
}
