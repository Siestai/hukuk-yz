"use client";

import { cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useState } from "react";

import type { Answer, CaseFacts, ChatMode, CitationRef } from "@/lib/chat-types";
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
        <article className="@container overflow-hidden rounded-md border border-border bg-surface">
            <header
                className={cn(
                    "px-4 py-3",
                    definite ? "bg-high-soft text-high" : "bg-medium-soft text-medium",
                )}
            >
                <p className="flex items-center gap-2 font-semibold">
                    <span aria-hidden="true" className="size-2.5 rounded-sm bg-current" />
                    {t(`status.${answer.status}`)}
                </p>
                <p className="text-sm">{answer.status_note}</p>
            </header>
            <div className="grid gap-4 p-4">
                <h3 className="font-serif text-xl font-semibold leading-snug text-ink">
                    {answer.headline}
                </h3>
                <div className="flex flex-wrap gap-2">
                    {answer.fact_chips.map((chip) => {
                        const className = cn(
                            "inline-flex min-h-8 items-center rounded-md px-2.5 text-sm font-medium",
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
                                    "focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:min-h-11",
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
                            className="min-h-8 rounded-md bg-primary-soft px-2.5 text-sm font-semibold text-primary focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:min-h-11"
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
            </div>
            {definite ? null : (
                <FoldSection title={t("missing")} open>
                    <ul className="grid gap-3">
                        {answer.missing_info.map((info, index) => (
                            <li key={index} className="font-serif text-ink">
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
                <div className="grid gap-3 border-t border-line p-4">
                    <HoldingMap rows={answer.holding_map.rows} onOpenCitation={onOpenCitation} />
                    <p className="wrap-anywhere font-serif text-lg leading-relaxed text-ink">
                        {answer.holding_map.reasoning_summary}
                    </p>
                    <CitationList
                        citations={answer.holding_map.citations}
                        onOpen={onOpenCitation}
                    />
                </div>
            ) : (
                <ul className="grid gap-4 border-t border-line p-4">
                    {points.map((point, index) => (
                        <li key={index} className="flex gap-3">
                            <span
                                aria-hidden="true"
                                className="mt-2.5 size-1.5 shrink-0 rounded-sm bg-ink-3"
                            />
                            <div className="min-w-0">
                                <p className="wrap-anywhere font-serif text-lg leading-relaxed text-ink">
                                    {point.text}
                                </p>
                                <CitationList citations={point.citations} onOpen={onOpenCitation} />
                            </div>
                        </li>
                    ))}
                </ul>
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
            <footer className="grid gap-0.5 border-t border-line px-4 py-3 text-xs text-ink-3">
                <p>
                    <span className="font-semibold">{t("appliedLaw")}</span>{" "}
                    {answer.applied_law_text}
                </p>
                <p>{answer.disclaimer}</p>
            </footer>
        </article>
    );
}
