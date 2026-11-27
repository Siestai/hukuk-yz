"use client";

import { Button, Card, Input, Progress } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";

import type {
    CitationRef,
    Clarification,
    ClarificationAnswer,
    ClarificationQuestion,
    Reply,
} from "@/lib/chat-types";
import { useDisplayValue } from "@/lib/use-display-value";
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
    const progressId = useId();
    const display = useDisplayValue();

    // The next question replaces the last one under the user's finger or cursor: move focus to
    // it so a screen reader reads it. Also on the first question, when the turn arrives.
    useEffect(() => {
        heading.current?.focus();
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

    const answered = questions.flatMap((q) => {
        const value = given[q.id];
        if (!value) return [];
        const text = value.unknown
            ? t("unknown")
            : (q.input.options.find((o) => o.value === value.value)?.label ??
              display(value.value ?? ""));
        return [{ id: q.id, label: q.text, text }];
    });

    return (
        <>
            {answered.length > 0 ? (
                <ul className="grid">
                    {answered.map((item) => (
                        <li
                            key={item.id}
                            className="flex min-h-12 min-w-0 animate-rise items-center gap-3 border-b border-line px-2 py-3"
                        >
                            <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5 shrink-0">
                                <circle cx="10" cy="10" r="9" className="fill-primary" />
                                <path
                                    d="M5.5 10.5l3 3 6-6.5"
                                    fill="none"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    className="stroke-primary-foreground"
                                />
                            </svg>
                            <span className="sr-only">{t("answered")}: </span>
                            <span
                                title={item.label}
                                className="min-w-0 max-w-1/2 truncate text-sm text-ink-2"
                            >
                                {item.label}
                            </span>
                            <span className="sr-only">: </span>
                            <span
                                title={item.text}
                                className="min-w-0 flex-1 truncate text-right font-serif text-lg text-ink"
                            >
                                {item.text}
                            </span>
                        </li>
                    ))}
                </ul>
            ) : null}
            <Card className="grid animate-rise gap-4 p-4 sm:p-6">
                <div className="flex items-center justify-between gap-4">
                    <p
                        id={progressId}
                        aria-live="polite"
                        className="text-sm font-semibold whitespace-nowrap text-high"
                    >
                        {t("progress", { index: position + 1, total: questions.length })}
                    </p>
                    <Progress
                        value={position + 1}
                        max={questions.length}
                        aria-labelledby={progressId}
                        className="h-1.5 max-w-40 flex-1"
                    />
                </div>
                <h3
                    ref={heading}
                    tabIndex={-1}
                    className="wrap-anywhere font-serif text-2xl leading-snug font-medium tracking-tight text-ink focus:outline-none"
                >
                    {question.text}
                </h3>
                <details className="group border-t border-line text-sm text-ink-2">
                    <summary className="flex min-h-12 cursor-pointer list-none items-center gap-2 rounded-md font-semibold text-ink focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                        {t("why")}
                        <svg
                            aria-hidden="true"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2}
                            strokeLinecap="round"
                            className="size-4 transition-transform group-open:rotate-180"
                        >
                            <path d="M6 9l6 6 6-6" />
                        </svg>
                    </summary>
                    <p className="wrap-anywhere">{question.why}</p>
                    <CitationList citations={question.source_refs} onOpen={onOpenCitation} />
                </details>
                <div className="grid gap-3">
                    {question.input.kind !== "choice" && (
                        <ValueForm
                            key={question.id}
                            kind={question.input.kind}
                            max={question.input.max_date ?? undefined}
                            label={question.text}
                            disabled={busy}
                            onSubmit={choose}
                        />
                    )}
                    {question.input.options.map((option, index) => (
                        <Button
                            key={option.value}
                            type="button"
                            variant="outline"
                            size="lg"
                            disabled={busy}
                            className="min-h-14 justify-start gap-3 whitespace-normal py-3 text-left text-base font-medium"
                            onClick={() => choose(option.value)}
                        >
                            <span
                                aria-hidden="true"
                                className="grid size-7 shrink-0 place-items-center rounded-md border border-input bg-bg text-xs font-bold text-ink-2"
                            >
                                {String.fromCharCode(65 + index)}
                            </span>
                            {option.label}
                        </Button>
                    ))}
                    <Button
                        type="button"
                        variant="ghost"
                        size="lg"
                        disabled={busy}
                        className="min-h-14 justify-start border border-dashed border-input text-base font-medium text-ink-2"
                        onClick={unknown}
                    >
                        {t("unknown")}
                    </Button>
                </div>
            </Card>
            <div className="sticky bottom-0 -mx-4 bg-bg px-4 pt-2 pb-safe-3 text-center">
                <Button
                    type="button"
                    variant="ghost"
                    disabled={busy}
                    className="min-h-11 font-semibold text-ink-2 underline underline-offset-4"
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
    max,
    label,
    disabled,
    onSubmit,
}: {
    kind: keyof typeof INPUT_TYPE;
    /** The latest date accepted (ISO), for a date whose fact cannot lie ahead. */
    max?: string;
    label: string;
    disabled: boolean;
    onSubmit: (value: string) => void;
}) {
    const t = useTranslations("chat.question");
    const [value, setValue] = useState("");
    const hintId = useId();
    const errorId = useId();
    // An input type=date always yields YYYY-MM-DD (or ""), so comparing the ISO strings is safe.
    const tooLate = kind === "date" && max !== undefined && value > max;
    const maxLabel =
        max !== undefined ? new Date(`${max}T00:00`).toLocaleDateString("tr-TR") : undefined;
    function submit(event: FormEvent) {
        event.preventDefault();
        if (value.trim() && !tooLate) onSubmit(value.trim());
    }
    return (
        <form onSubmit={submit} className="grid gap-2">
            <div className="flex gap-2">
                <Input
                    type={INPUT_TYPE[kind]}
                    inputMode={kind === "number" ? "decimal" : undefined}
                    value={value}
                    max={kind === "date" ? max : undefined}
                    onChange={(event) => setValue(event.target.value)}
                    aria-label={label}
                    aria-describedby={kind === "date" ? (tooLate ? errorId : hintId) : undefined}
                    aria-invalid={tooLate || undefined}
                    disabled={disabled}
                    className="h-12 bg-bg text-base pointer-coarse:h-12"
                />
                <Button
                    type="submit"
                    size="lg"
                    className="h-12 text-base font-semibold pointer-coarse:h-12"
                    disabled={disabled || !value.trim() || tooLate}
                >
                    {t("next")}
                </Button>
            </div>
            {tooLate && maxLabel !== undefined ? (
                <p id={errorId} role="alert" className="text-sm text-low">
                    {t("dateTooLate", { max: maxLabel })}
                </p>
            ) : (
                kind === "date" && (
                    <p id={hintId} className="text-xs text-ink-2">
                        {maxLabel !== undefined
                            ? t("dateHintPast", { max: maxLabel })
                            : t("dateHint")}
                    </p>
                )
            )}
        </form>
    );
}
