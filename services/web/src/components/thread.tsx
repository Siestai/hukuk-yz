"use client";

import { useErrorMessage } from "@hukuk/web-core/hooks/use-error-message";
import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useRef } from "react";

import type { LiveTurn } from "@/lib/chat-state";
import type { ChatMode, CitationRef, Reply, Turn } from "@/lib/chat-types";
import type { Failure } from "@/lib/use-chat-session";
import { AnswerView } from "./answer-view";
import { FactsCard } from "./facts-card";
import { FeedbackBar } from "./feedback-bar";
import { QuestionCard } from "./question-card";
import { UserBubble } from "./user-bubble";

type Props = {
    turns: Turn[];
    live: LiveTurn | null;
    /** What a broken stream had delivered before it failed. */
    partial: LiveTurn | null;
    failure: Failure | null;
    mode: ChatMode;
    onSend: (reply: Reply) => void;
    onRetry: () => void;
    /** `asOf`: the law date of the answer the citation belongs to; absent: today. */
    onOpenCitation: (citation: CitationRef, asOf?: string) => void;
};

/** The questions the user was asked last: the clarification of the turn before `index`. */
function openQuestions(turns: Turn[], index: number) {
    return turns[index - 1]?.clarification?.questions ?? [];
}

/** True when the last turn asks something that has no reply yet. */
export function hasOpenQuestions(turns: Turn[], live: LiveTurn | null): boolean {
    return live === null && Boolean(turns.at(-1)?.clarification);
}

export function Thread({
    turns,
    live,
    partial,
    failure,
    mode,
    onSend,
    onRetry,
    onOpenCitation,
}: Props) {
    const t = useTranslations("chat");
    const errorMessage = useErrorMessage();
    const last = useRef<HTMLDivElement>(null);
    const busy = live !== null;

    // A new turn starts at the top of the screen: an answer is read from its first line.
    useEffect(() => {
        last.current?.scrollIntoView?.({ block: "start" });
    }, [turns.length]);

    return (
        <>
            {turns.map((turn, index) => {
                const latest = index === turns.length - 1;
                const correct =
                    latest && !busy ? (message: string) => onSend({ text: message }) : undefined;
                return (
                    <div key={turn.id} ref={latest ? last : undefined} className="grid gap-4">
                        {turn.role === "user" ? (
                            <UserBubble turn={turn} questions={openQuestions(turns, index)} />
                        ) : (
                            <>
                                {turn.facts && !turn.answer ? (
                                    <FactsCard facts={turn.facts} onCorrect={correct} />
                                ) : null}
                                {turn.clarification && latest && !busy ? (
                                    <QuestionCard
                                        key={turn.id}
                                        clarification={turn.clarification}
                                        busy={busy}
                                        onReply={onSend}
                                        onOpenCitation={(citation) => onOpenCitation(citation)}
                                    />
                                ) : null}
                                {turn.answer ? (
                                    <>
                                        <AnswerView
                                            answer={turn.answer}
                                            mode={mode}
                                            facts={turn.facts ?? null}
                                            onCorrect={correct}
                                            onOpenCitation={(citation) =>
                                                onOpenCitation(
                                                    citation,
                                                    turn.answer?.applied_law_date,
                                                )
                                            }
                                        />
                                        <FeedbackBar turnId={turn.id} answer={turn.answer} />
                                    </>
                                ) : null}
                            </>
                        )}
                    </div>
                );
            })}
            {live ? (
                <div className="grid gap-4">
                    {live.facts ? <FactsCard facts={live.facts} /> : null}
                    <p role="status" className="text-sm text-ink-2">
                        {live.label ? t("step", { label: live.label }) : null}
                    </p>
                </div>
            ) : null}
            {partial?.facts ? <FactsCard facts={partial.facts} /> : null}
            <div role="alert">
                {failure ? (
                    <div className="grid justify-items-start gap-2 rounded-md bg-low-soft px-4 py-3 text-sm text-low">
                        <p>
                            {failure.code === "upstream_unavailable"
                                ? t("stream.connectionLost")
                                : null}{" "}
                            {errorMessage(failure.code, failure.params)}
                        </p>
                        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
                            {t("stream.retry")}
                        </Button>
                    </div>
                ) : null}
            </div>
        </>
    );
}
