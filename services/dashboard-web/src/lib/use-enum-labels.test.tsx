import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import { readRepoFile, reasonCodes } from "@/test/reason-codes";
import { COURTS } from "./queue-params";
import { useEnumLabels } from "./use-enum-labels";

function courtValues(): string[] {
    const block = /^class Court\(PgEnum\):\n([\s\S]*?)^\n/m.exec(
        readRepoFile("services/app/app/models/common.py"),
    );
    return [...(block?.[1] ?? "").matchAll(/^\s+\w+ = "(\w+)"/gm)].map((m) => String(m[1]));
}

function wrapper({ children }: { children: ReactNode }) {
    return (
        <NextIntlClientProvider locale="tr" messages={messages}>
            {children}
        </NextIntlClientProvider>
    );
}

describe("enum labels", () => {
    it("reads the reason codes from confidence.py", () => {
        expect(reasonCodes().length).toBeGreaterThan(20);
    });

    it("has a Turkish label for every reason code of confidence.py", () => {
        const labelled = Object.keys(messages.enums.reason);
        expect(reasonCodes().filter((code) => !labelled.includes(code))).toEqual([]);
        expect(labelled.filter((code) => !reasonCodes().includes(code))).toEqual([]);
    });

    it("has a label for every Court value of the API and COURTS lists them all", () => {
        expect(courtValues()).toEqual([...COURTS]);
        for (const court of COURTS) expect(messages.enums.court).toHaveProperty(court);
    });

    it("labels band, court and reason, with the unreadable court as Belirsiz", () => {
        const { result } = renderHook(() => useEnumLabels(), { wrapper });
        expect(result.current.band("high")).toBe("Yüksek");
        expect(result.current.court("aihm")).toBe("AİHM");
        expect(result.current.court("")).toBe("Belirsiz");
        expect(result.current.reason("missing_karar_no")).toBe("Karar no yok");
    });

    it("falls back to the raw code for an unknown value", () => {
        const { result } = renderHook(() => useEnumLabels(), { wrapper });
        expect(result.current.reason("brand_new")).toBe("brand_new");
        expect(result.current.isKnownReason("brand_new")).toBe(false);
        expect(result.current.isKnownReason("duplicate_of")).toBe(true);
        expect(result.current.court("mars")).toBe("mars");
    });
});
