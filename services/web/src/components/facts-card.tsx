"use client";

import { Button, Card, Input } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState, type FormEvent } from "react";

import type { CaseFacts, Fact } from "@/lib/chat-types";
import { useDisplayValue } from "@/lib/use-display-value";

/**
 * "Anladığım olay": what the agent understood. Unknown values stand out; on the latest turn a
 * value can be tapped and corrected, and the correction goes out as a new message.
 */
export function FactsCard({
    facts,
    onCorrect,
}: {
    facts: CaseFacts;
    /** Absent: the card is read-only (an older turn). */
    onCorrect?: (message: string) => void;
}) {
    const t = useTranslations("chat.facts");
    const [editing, setEditing] = useState<string | null>(null);
    const display = useDisplayValue();

    function submit(event: FormEvent<HTMLFormElement>, fact: Fact) {
        event.preventDefault();
        const value = String(new FormData(event.currentTarget).get("value") ?? "").trim();
        if (!value) return;
        setEditing(null);
        onCorrect?.(t("correction", { label: fact.label, value }));
    }

    return (
        <Card className="animate-rise p-4 sm:p-6">
            <h3 className="font-serif text-xl font-medium text-ink">{t("title")}</h3>
            <dl className="mt-3 grid grid-cols-1 divide-y divide-line">
                {facts.facts.map((fact) => (
                    <div
                        key={fact.key}
                        className="grid grid-cols-1 gap-1 py-3 first:pt-0 last:pb-0"
                    >
                        <dt className="text-xs font-semibold text-ink-2">{fact.label}</dt>
                        <dd className="min-w-0">
                            {editing === fact.key ? (
                                <form
                                    onSubmit={(event) => submit(event, fact)}
                                    className="flex flex-wrap items-center gap-2"
                                >
                                    <Input
                                        name="value"
                                        defaultValue={display(fact.value ?? "")}
                                        aria-label={t("editValue", { label: fact.label })}
                                        className="min-w-36 flex-1 bg-bg text-base"
                                        autoFocus
                                    />
                                    <Button type="submit" size="sm" className="font-semibold">
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
    const display = useDisplayValue();
    const unknown = fact.status === "unknown";
    const className = unknown ? "italic text-ink-2" : "text-ink";
    const text = unknown ? unknownText : display(fact.value ?? "");
    if (!onEdit)
        return <span className={`${className} wrap-anywhere font-serif text-lg`}>{text}</span>;
    return (
        <button
            type="button"
            onClick={onEdit}
            aria-label={`${editLabel}: ${text}`}
            className={`${className} wrap-anywhere min-h-11 rounded-md text-left font-serif text-lg underline decoration-line-strong decoration-dotted underline-offset-4 focus-visible:outline-2 focus-visible:outline-ring`}
        >
            {text}
        </button>
    );
}
