import { renderHook } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import { readRepoFile, reasonCodes, warningCodes } from "@/test/reason-codes";
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

    it("keeps the constraint name of a bulk failure and shows unknown reasons as they came", () => {
        const { result } = renderHook(() => useEnumLabels(), { wrapper });
        expect(result.current.bulkFailure("database constraint violated: ix_x")).toBe(
            `${messages.enums.bulkFailure.constraint_violated}: ix_x`,
        );
        expect(result.current.bulkFailure("a brand new reason")).toBe("a brand new reason");
    });

    it("has a Turkish label for every reason code of confidence.py", () => {
        const labelled = Object.keys(messages.enums.reason);
        expect(reasonCodes().filter((code) => !labelled.includes(code))).toEqual([]);
        expect(labelled.filter((code) => !reasonCodes().includes(code))).toEqual([]);
    });

    it("has a Turkish label for every warning code the parser and the loader emit", () => {
        const labelled = Object.keys(messages.enums.warning);
        expect(warningCodes().length).toBeGreaterThan(15);
        expect(warningCodes().filter((code) => !labelled.includes(code))).toEqual([]);
        expect(labelled.filter((code) => !warningCodes().includes(code))).toEqual([]);
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

    it("labels court level, outcome, source status and warnings, keeping a warning's detail", () => {
        const { result } = renderHook(() => useEnumLabels(), { wrapper });
        expect(result.current.courtLevel("hgk_iddk")).toBe(messages.enums.courtLevel.hgk_iddk);
        expect(result.current.outcome("duzelterek_onama")).toBe("Düzelterek onama");
        expect(result.current.sourceStatus("analyzed")).toBe("Onay bekliyor");
        expect(result.current.warning("multiple_esas_candidates:2010/1")).toBe(
            "Birden çok esas no adayı:2010/1",
        );
        expect(result.current.isKnownWarning("multiple_esas_candidates:2010/1")).toBe(true);
        expect(result.current.isKnownWarning("brand_new")).toBe(false);
        expect(result.current.warning("brand_new")).toBe("brand_new");
    });

    it("falls back to the raw code for an unknown value", () => {
        const { result } = renderHook(() => useEnumLabels(), { wrapper });
        expect(result.current.reason("brand_new")).toBe("brand_new");
        expect(result.current.isKnownReason("brand_new")).toBe(false);
        expect(result.current.isKnownReason("duplicate_of")).toBe(true);
        expect(result.current.court("mars")).toBe("mars");
    });
});
