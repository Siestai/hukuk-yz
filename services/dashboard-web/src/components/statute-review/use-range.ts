import { useTranslations } from "next-intl";

import { useDates } from "@/lib/use-dates";

/** "10.06.2003 → 15.09.2014"; no end is "bugün", no start (a gap) the statute's own entry into force. */
export function useRange() {
    const t = useTranslations("review.statutes.timeline");
    const { date } = useDates();
    return (from: string | null, to: string | null) =>
        t("range", {
            from: from ? date(from) : t("fromStart"),
            to: to ? date(to) : t("today"),
        });
}
