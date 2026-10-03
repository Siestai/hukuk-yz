import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider, useFormatter } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { formats, timeZone } from "./formats";

function wrapper({ children }: { children: ReactNode }) {
    return (
        <NextIntlClientProvider locale="tr" formats={formats} timeZone={timeZone}>
            {children}
        </NextIntlClientProvider>
    );
}

describe("formats", () => {
    it("formats dates and numbers the Turkish way", () => {
        const { result } = renderHook(() => useFormatter(), { wrapper });
        const format = result.current;
        expect(format.dateTime(new Date("2026-10-03T21:30:00Z"), "dateTime")).toBe(
            "04.10.2026 00:30",
        );
        expect(format.dateTime(new Date("2026-10-03T09:00:00Z"), "date")).toBe("03.10.2026");
        expect(format.number(1234.5, "score")).toBe("1.234,50");
        expect(format.number(6342, "integer")).toBe("6.342");
    });
});
