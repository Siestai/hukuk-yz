import { useFormatter } from "next-intl";

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Shows a fact or answer value as the user reads it: an ISO date as DD.MM.YYYY, anything else as given. */
export function useDisplayValue() {
    const format = useFormatter();
    return (value: string) => {
        const day = new Date(value);
        return ISO_DATE.test(value) && !Number.isNaN(day.getTime())
            ? format.dateTime(day, "date")
            : value;
    };
}
