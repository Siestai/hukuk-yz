import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import type { StatuteQueueParams } from "@/lib/statute-queue-params";
import { listItem } from "@/test/statute-fixtures";
import { StatuteBulkApprove } from "./statute-bulk-approve";

vi.mock("next-intl/server", async () => {
    const intl = await import("next-intl");
    return {
        getTranslations: async (ns: string) =>
            intl.createTranslator({ locale: "tr", messages, namespace: ns as never }),
    };
});

const params: StatuteQueueParams = { kind: "statute", statute: "4857", band: "high", page: 1 };
type Props = Record<string, unknown>;

describe("StatuteBulkApprove", () => {
    it("hands the button the total and the first five articles, worded for the dialog", async () => {
        const items = Array.from({ length: 7 }, (_, n) => ({
            ...listItem,
            extraction_id: `e${n}`,
            article_no: n === 1 ? "Geçici 8" : String(n + 1),
            heading: n === 2 ? null : listItem.heading,
        }));
        const element = (await StatuteBulkApprove({
            params,
            list: Promise.resolve({ data: { total: 130, items } }),
        })) as ReactElement<Props>;
        expect(element.props).toMatchObject({ params, total: 130, unavailable: false });
        const sample = element.props.sample as { title: string; note: string }[];
        expect(sample).toHaveLength(5);
        expect(sample[0]).toEqual({
            id: "e0",
            title: "m. 1 · Feshin geçerli sebebe dayandırılması",
            esasNo: "",
            kararNo: "",
            note: "3 sürüm · 1 boşluk",
        });
        expect(sample[1]?.title).toBe("Geçici 8 · Feshin geçerli sebebe dayandırılması");
        expect(sample[2]?.title).toBe("m. 3");
    });

    it("is unavailable without a list, or when the list failed", async () => {
        const waiting = (await StatuteBulkApprove({ params })) as ReactElement<Props>;
        expect(waiting.props).toMatchObject({ unavailable: true, total: 0, sample: [] });
        const failed = (await StatuteBulkApprove({
            params,
            list: Promise.resolve({ error: { code: "forbidden", params: {} } }),
        })) as ReactElement<Props>;
        expect(failed.props.unavailable).toBe(true);
    });
});
