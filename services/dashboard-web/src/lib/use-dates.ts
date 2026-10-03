import { useFormatter } from "next-intl";

import { formats } from "@/i18n/formats";

import { useCommon } from "./use-common";

/** Dates in the active locale. A date-only ISO value is midnight UTC; it is formatted in UTC so the calendar day never shifts. */
export function useDates() {
    const format = useFormatter();
    const { empty } = useCommon();
    return {
        date: (iso: string) =>
            /^\d{4}-\d{2}-\d{2}$/.test(iso)
                ? format.dateTime(new Date(iso), { ...formats.dateTime.date, timeZone: "UTC" })
                : iso || empty,
        dateTime: (iso: string) => {
            const value = new Date(iso);
            return Number.isNaN(value.getTime())
                ? empty
                : format.dateTime(value, formats.dateTime.dateTime);
        },
    };
}
