import { describe, expect, it } from "vitest";

import { bulkScope } from "./bulk-approve";
import type { QueueParams } from "./queue-params";
import {
    changeState,
    isStatuteState,
    parseState,
    stateDetailHref,
    stateHref,
    stateKey,
    stateStatus,
    stateTab,
} from "./queue-state";

const decisions: QueueParams = { band: "high", court: "bam", sort: "score_asc", page: 1 };
const statutes = parseState("statute", new URLSearchParams("kanun=5510&band=high"));

describe("queue state of either queue", () => {
    it("tells the two queues apart and parses each from its own URL", () => {
        expect(isStatuteState(decisions)).toBe(false);
        expect(isStatuteState(statutes)).toBe(true);
        expect(parseState("decision", new URLSearchParams("court=bam"))).toMatchObject({
            court: "bam",
        });
    });

    it("builds the list and detail links of the queue it belongs to", () => {
        expect(stateHref(decisions)).toBe("/?band=high&court=bam");
        expect(stateHref(statutes)).toBe("/mevzuat?kanun=5510&band=high");
        expect(stateDetailHref("e1", decisions, { pos: 2 })).toBe(
            "/kararlar/e1?band=high&court=bam&pos=2",
        );
        expect(stateDetailHref("e1", statutes, { pos: 2 })).toBe(
            "/mevzuat/e1?kanun=5510&band=high&pos=2",
        );
    });

    it("keys, tabs and changes each in its own way", () => {
        expect(stateKey(statutes)).toBe("kanun=5510&band=high");
        expect(stateStatus(statutes)).toBe("pending");
        expect(stateStatus(stateTab(statutes, "rejected"))).toBe("rejected");
        expect(stateStatus(stateTab(decisions, "approved"))).toBe("approved");
        expect(changeState(statutes, { band: undefined })).toMatchObject({
            kind: "statute",
            page: 1,
        });
        expect(changeState(decisions, { court: "aym" })).toMatchObject({ court: "aym" });
    });

    it("scopes a bulk run by the filters of decisions and by the statute of articles", () => {
        expect(bulkScope(decisions)).toEqual({
            filters: { court: "bam", reason: undefined, journal_issue: undefined, q: undefined },
        });
        expect(bulkScope(statutes)).toEqual({ statute: "5510" });
    });
});
