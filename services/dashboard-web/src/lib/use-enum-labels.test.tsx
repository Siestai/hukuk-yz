import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import { COURTS } from "./queue-params";
import { useEnumLabels } from "./use-enum-labels";

const ROOT = join(import.meta.dirname, "../../../..");
const read = (path: string) => readFileSync(join(ROOT, path), "utf8");

/** Keys of the `RULES` table of the confidence rules: every code a review can carry. */
function reasonCodes(): string[] {
    const source = read("services/app/app/loaders/confidence.py");
    const table = /^RULES[^\n]*= \{\n([\s\S]*?)^\}/m.exec(source)?.[1] ?? "";
    return [...table.matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => String(m[1]));
}

function courtValues(): string[] {
    const block = /^class Court\(PgEnum\):\n([\s\S]*?)^\n/m.exec(
        read("services/app/app/models/common.py"),
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
