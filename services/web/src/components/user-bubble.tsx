import { useTranslations } from "next-intl";

import type { ClarificationQuestion, Turn } from "@/lib/chat-types";

/** What the user sent: the question, the answers to the open questions, or the choice to skip them. */
export function UserBubble({
    turn,
    questions,
}: {
    turn: Turn;
    /** The questions that were open when the user answered. */
    questions: ClarificationQuestion[];
}) {
    const t = useTranslations("chat.user");
    const lines = turn.skipped
        ? [t("skipped")]
        : turn.clarification_answers
          ? turn.clarification_answers.map((given) => {
                const question = questions.find((q) => q.id === given.question_id);
                const option = question?.input.options.find((o) => o.value === given.value);
                return t("answer", {
                    question: question?.text ?? "",
                    answer: given.unknown ? t("unknown") : (option?.label ?? given.value ?? ""),
                });
            })
          : [turn.text ?? ""];
    return (
        <div className="ml-auto grid w-fit max-w-full justify-items-end gap-1 md:max-w-xl">
            <div className="grid gap-1 rounded-md bg-primary px-4 py-3 text-primary-foreground">
                {lines.map((line, index) => (
                    <p key={index} className="wrap-anywhere">
                        {line}
                    </p>
                ))}
            </div>
        </div>
    );
}
