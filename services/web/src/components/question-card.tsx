"use client";

import { Button, Card, Input, Progress } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useRef, useState, type FormEvent } from "react";

import type {
    CitationRef,
    Clarification,
    ClarificationAnswer,
    ClarificationQuestion,
    Reply,
} from "@/lib/chat-types";
import { CitationList } from "./citation-list";

const INPUT_TYPE = { date: "date", number: "number", text: "text" } as const;

/** The reply to the open questions: the answers given, "Bilmiyorum" for the rest, or a skip when nothing was given. */
export function clarificationReply(
    questions: ClarificationQuestion[],
    given: Record<string, ClarificationAnswer>,
): Reply {
    if (Object.keys(given).length === 0) return { skip: true };
    return {
        clarification_answers: questions.map(
            (q) => given[q.id] ?? { question_id: q.id, unknown: true },
        ),
    };
}

/**
 * One open question at a time ("Soru 1 / 5"): its options or input, always "Bilmiyorum", the
 * reason for asking with its sources. The answers go out together after the last question, or
 * when the user skips the rest.
 */
export function QuestionCard({
    clarification,
    busy,
    onReply,
    onOpenCitation,
}: {
    clarification: Clarification;
    busy: boolean;
    onReply: (reply: Reply) => void;
    onOpenCitation: (citation: CitationRef) => void;
}) {
    const t = useTranslations("chat.question");
    const { questions } = clarification;
    const [position, setPosition] = useState(0);
    const [given, setGiven] = useState<Record<string, ClarificationAnswer>>({});
    const question = questions[position];
    const heading = useRef<HTMLHeadingElement>(null);

    // The next question replaces the last one under the user's finger or cursor: move focus to
    // it so a screen reader reads it. Not on the first question, which arrives with the turn.
    useEffect(() => {
        if (position > 0) heading.current?.focus();
    }, [position]);

    if (!question) return null;

    function answer(value: ClarificationAnswer) {
        const next = { ...given, [value.question_id]: value };
        setGiven(next);
        if (position + 1 < questions.length) setPosition(position + 1);
        else onReply(clarificationReply(questions, next));
    }
    const choose = (value: string) => answer({ question_id: question.id, value, unknown: false });
    const unknown = () => answer({ question_id: question.id, unknown: true });

    return (
        <>
            <Card className="grid gap-4 p-4">
                <Progress
                    value={position + 1}
                    max={questions.length}
                    aria-label={t("progress", { index: position + 1, total: questions.length })}
                />
                <div>
                    <p className="text-sm text-ink-2">
                        {t("progress", { index: position + 1, total: questions.length })}
                    </p>
                    <h3
                        ref={heading}
                        tabIndex={-1}
                        className="mt-1 font-serif text-lg font-semibold text-ink focus:outline-none"
                    >
                        {question.text}
                    </h3>
                </div>
                <div className="grid gap-2">
                    {question.input.kind === "choice" ? (
                        question.input.options.map((option) => (
                            <Button
                                key={option.value}
                                type="button"
                                variant="outline"
                                size="lg"
                                disabled={busy}
                                className="h-12 justify-start text-base pointer-coarse:h-12"
                                onClick={() => choose(option.value)}
                            >
                                {option.label}
                            </Button>
                        ))
                    ) : (
                        <ValueForm
                            key={question.id}
                            kind={question.input.kind}
                            label={question.text}
                            disabled={busy}
                            onSubmit={choose}
                        />
                    )}
                    <Button
                        type="button"
                        variant="outline"
                        size="lg"
                        disabled={busy}
                        className="h-12 justify-start text-base text-ink-3 pointer-coarse:h-12"
                        onClick={unknown}
                    >
                        {t("unknown")}
                    </Button>
                </div>
                <div className="text-sm text-ink-2">
                    <p className="wrap-anywhere">{t("why", { why: question.why })}</p>
                    <CitationList citations={question.source_refs} onOpen={onOpenCitation} />
                </div>
            </Card>
            <div className="sticky bottom-0 -mx-4 bg-bg px-4 pt-2 pb-safe-3 text-center">
                <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    className="font-semibold text-primary"
                    onClick={() => onReply(clarificationReply(questions, given))}
                >
                    {t("skip")}
                </Button>
            </div>
        </>
    );
}

function ValueForm({
    kind,
    label,
    disabled,
    onSubmit,
}: {
    kind: keyof typeof INPUT_TYPE;
    label: string;
    disabled: boolean;
    onSubmit: (value: string) => void;
}) {
    const t = useTranslations("chat.question");
    const [value, setValue] = useState("");
    function submit(event: FormEvent) {
        event.preventDefault();
        if (value.trim()) onSubmit(value.trim());
    }
    return (
        <form onSubmit={submit} className="flex gap-2">
            <Input
                type={INPUT_TYPE[kind]}
                inputMode={kind === "number" ? "decimal" : undefined}
                value={value}
                onChange={(event) => setValue(event.target.value)}
                aria-label={label}
                disabled={disabled}
                className="h-12 pointer-coarse:h-12"
            />
            <Button type="submit" size="lg" disabled={disabled || !value.trim()}>
                {t("next")}
            </Button>
        </form>
    );
}
