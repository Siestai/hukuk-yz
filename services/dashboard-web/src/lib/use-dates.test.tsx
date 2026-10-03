import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import { formats, timeZone } from "@/i18n/formats";
import { useDates } from "./use-dates";

function wrapper({ children }: { children: ReactNode }) {
    return (
        <NextIntlClientProvider
            locale="tr"
            messages={messages}
            formats={formats}
            timeZone={timeZone}
        >
            {children}
        </NextIntlClientProvider>
    );
}

describe("useDates", () => {
    const dates = () => renderHook(() => useDates(), { wrapper }).result.current;

    it("formats a date-only value without shifting the day", () => {
        expect(dates().date("2021-03-05")).toBe("05.03.2021");
    });

    it("formats a timestamp in Istanbul time", () => {
        expect(dates().dateTime("2026-10-02T21:30:00Z")).toBe("03.10.2026 00:30");
    });

    it("returns the empty marker instead of throwing for an invalid timestamp", () => {
        expect(dates().dateTime("not a date")).toBe(messages.common.empty);
        expect(dates().dateTime("")).toBe(messages.common.empty);
    });

    it("keeps an unparsable date as it is and shows the marker for an empty one", () => {
        expect(dates().date("5 Mart")).toBe("5 Mart");
        expect(dates().date("")).toBe(messages.common.empty);
    });
});
