import { useTranslations } from "next-intl";

/** The help text of a reason code of a statute article, or `undefined` for a code the messages do not know. */
export function useStatuteReasonHelp() {
    const root = useTranslations();
    return (code: string) => {
        const key = `review.statutes.help.reason.${code}`;
        return root.has(key) ? root(key) : undefined;
    };
}
