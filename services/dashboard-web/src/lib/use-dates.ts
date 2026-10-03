import { useFormatter } from "next-intl";

import { formats } from "@/i18n/formats";

/** Dates in the active locale. A date-only ISO value is midnight UTC; it is formatted in UTC so the calendar day never shifts. */
export function useDates() {
    const format = useFormatter();
    return {
        date: (iso: string) =>
            /^\d{4}-\d{2}-\d{2}$/.test(iso)
                ? format.dateTime(new Date(iso), { ...formats.dateTime.date, timeZone: "UTC" })
                : iso || "-",
        dateTime: (iso: string) => format.dateTime(new Date(iso), formats.dateTime.dateTime),
    };
}
