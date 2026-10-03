import type { Formats } from "next-intl";

export const timeZone = "Europe/Istanbul";

export const formats = {
    dateTime: {
        date: { day: "2-digit", month: "2-digit", year: "numeric" },
        dateTime: {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        },
    },
    number: {
        integer: { maximumFractionDigits: 0 },
        score: { minimumFractionDigits: 2, maximumFractionDigits: 2 },
    },
} satisfies Formats;
