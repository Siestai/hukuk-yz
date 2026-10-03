import type { ReactElement } from "react";
import { describe, expect, it } from "vitest";

import type { components } from "@/lib/api/schema";
import type { QueueParams } from "@/lib/queue-params";
import { QueueBulkApprove } from "./queue-bulk-approve";

type Item = components["schemas"]["ReviewListItem"];
const params: QueueParams = { band: "high", sort: "score_asc", page: 1 };
const item = (n: number) =>
    ({
        extraction_id: `e${n}`,
        title: `T${n}`,
        esas_no: `2020/${n}`,
        karar_no: `2021/${n}`,
    }) as Item;

describe("QueueBulkApprove", () => {
    it("hands the button the total of the list and its first five records", async () => {
        const items = [1, 2, 3, 4, 5, 6, 7].map(item);
        const element = (await QueueBulkApprove({
            params,
            list: Promise.resolve({ data: { total: 130, items } }),
        })) as ReactElement<Record<string, unknown>>;
        expect(element.props).toMatchObject({ params, total: 130, unavailable: false });
        expect(element.props.sample).toEqual([
            { id: "e1", title: "T1", esasNo: "2020/1", kararNo: "2021/1" },
            ...[2, 3, 4, 5].map((n) => ({
                id: `e${n}`,
                title: `T${n}`,
                esasNo: `2020/${n}`,
                kararNo: `2021/${n}`,
            })),
        ]);
    });

    it("is unavailable without a list, or when the list failed", async () => {
        const waiting = (await QueueBulkApprove({ params })) as ReactElement<
            Record<string, unknown>
        >;
        expect(waiting.props).toMatchObject({ unavailable: true, total: 0, sample: [] });
        const failed = (await QueueBulkApprove({
            params,
            list: Promise.resolve({ error: { code: "forbidden", params: {} } }),
        })) as ReactElement<Record<string, unknown>>;
        expect(failed.props.unavailable).toBe(true);
    });
});
