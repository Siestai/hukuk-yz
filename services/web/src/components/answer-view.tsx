"use client";

import { cn } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";
import { useState } from "react";

import type { Answer, CaseFacts, ChatMode, CitationRef, SourceGap } from "@/lib/chat-types";
import { useDisplayValue } from "@/lib/use-display-value";
import { CitationList } from "./citation-list";
import { FactsCard } from "./facts-card";
import { FoldSection } from "./fold-section";
import { HoldingMap } from "./holding-map";

/**
 * One `Answer` in the mode the user picked. The mode only changes what is shown: short keeps the
 * first points, detailed all of them, reasoned replaces the points with the holding map.
 */
export function AnswerView({
    answer,
    mode,
    facts,
    onOpenCitation,
    onCorrect,
}: {
    answer: Answer;
    mode: ChatMode;
    /** The case the answer rests on, for the "Düzenle" editor; absent: no editing. */
    facts: CaseFacts | null;
    onOpenCitation: (citation: CitationRef) => void;
    onCorrect?: (message: string) => void;
}) {
    const t = useTranslations("chat.answer");
    const [editing, setEditing] = useState(false);
    const definite = answer.status === "definite";
    const points =
        mode === "short" ? answer.points.slice(0, answer.short_point_count) : answer.points;
    const reads = [
        answer.read_sources.statute_articles > 0 &&
            t("readsStatutes", { count: answer.read_sources.statute_articles }),
        answer.read_sources.decisions > 0 &&
            t("readsDecisions", { count: answer.read_sources.decisions }),
        answer.read_sources.admin_acts > 0 &&
            t("readsAdminActs", { count: answer.read_sources.admin_acts }),
    ].filter(Boolean);

    return (
        <article className="@container grid min-w-0 animate-rise gap-4 overflow-hidden rounded-card border border-border bg-surface p-4 sm:p-6">
            <header className="grid gap-2">
                <p
                    className={cn(
                        "inline-flex min-h-8 items-center gap-2 justify-self-start rounded-md px-3 text-sm font-bold",
                        definite ? "bg-high-soft text-high" : "bg-medium-soft text-medium",
                    )}
                >
                    <span aria-hidden="true" className="size-2.5 rounded-sm bg-current" />
                    {t(`status.${answer.status}`)}
                </p>
                <p className="text-xs leading-relaxed text-ink-2">{answer.status_note}</p>
            </header>
            <h3 className="wrap-anywhere font-serif text-xl leading-snug font-medium tracking-tight text-pretty text-ink sm:text-2xl">
                {answer.headline}
            </h3>
            <div className="flex flex-wrap gap-2">
                {answer.fact_chips.map((chip) => {
                    const className = cn(
                        "inline-flex min-h-8 items-center rounded-md px-3 text-sm font-medium",
                        chip.status === "unknown"
                            ? "bg-medium-soft text-medium"
                            : "bg-sunken text-ink-2",
                    );
                    return facts && onCorrect ? (
                        <button
                            key={chip.fact_key}
                            type="button"
                            onClick={() => setEditing(true)}
                            className={cn(
                                className,
                                "min-h-11 focus-visible:outline-2 focus-visible:outline-ring",
                            )}
                        >
                            {chip.label}
                        </button>
                    ) : (
                        <span key={chip.fact_key} className={className}>
                            {chip.label}
                        </span>
                    );
                })}
                {facts && onCorrect ? (
                    <button
                        type="button"
                        onClick={() => setEditing((open) => !open)}
                        aria-expanded={editing}
                        className="lip lip-edge mb-0.5 min-h-11 rounded-md border border-primary-edge bg-primary-soft px-3 text-sm font-semibold text-high focus-visible:outline-2 focus-visible:outline-ring"
                    >
                        {t("edit")}
                    </button>
                ) : null}
            </div>
            {editing && facts && onCorrect ? (
                <FactsCard
                    facts={facts}
                    onCorrect={(message) => {
                        setEditing(false);
                        onCorrect(message);
                    }}
                />
            ) : null}
            {answer.source_gap ? (
                <div className="border-t border-line pt-4">
                    <SourceGapNote gap={answer.source_gap} />
                </div>
            ) : null}
            {definite || answer.missing_info.length === 0 ? null : (
                <FoldSection title={t("missing")} open>
                    <ul className="grid gap-3">
                        {answer.missing_info.map((info, index) => (
                            <li key={index} className="font-serif text-lg leading-relaxed text-ink">
                                <p className="wrap-anywhere">
                                    {info.condition}
                                    {": "}
                                    {info.result}
                                </p>
                                <CitationList citations={info.citations} onOpen={onOpenCitation} />
                            </li>
                        ))}
                    </ul>
                </FoldSection>
            )}
            {mode === "reasoned" ? (
                <div className="grid gap-3 border-t border-line pt-4">
                    {/* The source-gap answer may have no verified row to show. */}
                    {answer.holding_map.rows.length ? (
                        <HoldingMap
                            rows={answer.holding_map.rows}
                            onOpenCitation={onOpenCitation}
                        />
                    ) : null}
                    <p className="wrap-anywhere font-serif text-lg leading-relaxed text-ink">
                        {answer.holding_map.reasoning_summary}
                    </p>
                    <CitationList
                        citations={answer.holding_map.citations}
                        onOpen={onOpenCitation}
                    />
                </div>
            ) : (
                <ol className="grid">
                    {points.map((point, index) => (
                        <li
                            key={index}
                            className="flex animate-rise gap-3 border-t border-line py-4 first:pb-4"
                        >
                            <span
                                aria-hidden="true"
                                className="w-7 shrink-0 font-serif text-xl leading-normal text-high"
                            >
                                {index + 1}
                            </span>
                            <div className="min-w-0">
                                <p className="wrap-anywhere mb-3 font-serif text-lg leading-relaxed text-ink">
                                    {point.text}
                                </p>
                                <CitationList citations={point.citations} onOpen={onOpenCitation} />
                            </div>
                        </li>
                    ))}
                </ol>
            )}
            {answer.calculations.map((calculation, index) => (
                <FoldSection
                    key={index}
                    title={t("calculation", { title: calculation.title })}
                    hint={t("needs", { needs: calculation.needs.join(", ") })}
                >
                    <ul className="list-disc pl-5 text-ink-2">
                        {calculation.needs.map((need, position) => (
                            <li key={position}>{need}</li>
                        ))}
                    </ul>
                </FoldSection>
            ))}
            <FoldSection title={t("reads")} hint={reads.join(", ")}>
                <CitationList citations={answer.read_sources.items} onOpen={onOpenCitation} />
            </FoldSection>
            <footer className="grid gap-0.5 border-t border-line pt-4 text-xs text-ink-2">
                <p>
                    <span className="font-semibold">{t("appliedLaw")}</span>{" "}
                    {answer.applied_law_text}
                </p>
                <p>{answer.disclaimer}</p>
            </footer>
        </article>
    );
}

/**
 * "Kaynak yetersiz": what a fallback lacked, one line each: the topic, the sources that could not
 * be read and why, what the user told, and the next step (the design comes later).
 */
export function SourceGapNote({ gap }: { gap: SourceGap }) {
    const t = useTranslations("chat.gap");
    const format = useFormatter();
    const display = useDisplayValue();
    const sources = gap.missing_sources.map((source) =>
        t("source", { ref: source.ref, reason: t(`reasons.${source.reason}`) }),
    );
    const facts = gap.given_facts.map((fact) =>
        t("fact", { label: fact.label, value: display(fact.value ?? "") }),
    );
    const lines = [
        t("topic", { topic: gap.topic }),
        sources.length > 0 ? t("missing", { sources: format.list(sources) }) : null,
        facts.length > 0 ? t("given", { facts: format.list(facts) }) : null,
        gap.next_step,
    ].filter((line) => line !== null);
    return (
        <ul aria-label={t("label")} className="grid gap-1 text-sm text-ink-2">
            {lines.map((line, index) => (
                <li key={index} className="wrap-anywhere">
                    {line}
                </li>
            ))}
        </ul>
    );
}
