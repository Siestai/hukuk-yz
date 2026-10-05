import { describe, expect, it } from "vitest";

import {
    apiQuery,
    changeQueueParams,
    detailHref,
    activeFilterCount,
    hasFilters,
    parseNotice,
    parsePosition,
    parseQueueParams,
    queueHref,
    serializeQueueParams,
    sortsFor,
    tabParams,
    type QueueParams,
} from "./queue-params";

const defaults: QueueParams = { sort: "score_asc", page: 1 };

describe("parseQueueParams", () => {
    it("falls back to the defaults for an empty URL", () => {
        expect(parseQueueParams(new URLSearchParams())).toEqual({
            band: undefined,
            court: undefined,
            reason: undefined,
            journalIssue: undefined,
            q: undefined,
            sort: "score_asc",
            page: 1,
        });
    });

    it("reads every parameter", () => {
        const query =
            "band=low&court=bam&reason=missing_karar_no&journal_issue=77&q=2019&sort=score_desc&page=3";
        expect(parseQueueParams(new URLSearchParams(query))).toEqual({
            band: "low",
            court: "bam",
            reason: "missing_karar_no",
            journalIssue: 77,
            q: "2019",
            sort: "score_desc",
            page: 3,
        });
    });

    it("reads Next's search params record and takes the first of repeated values", () => {
        const params = parseQueueParams({ band: ["medium", "low"], page: "2", q: undefined });
        expect(params).toMatchObject({ band: "medium", page: 2, q: undefined });
    });

    it.each([
        ["band", "band=huge"],
        ["court", "court=mars"],
        ["reason", "reason=Not%20A%20Code"],
        ["journalIssue", "journal_issue=abc"],
        ["journalIssue", "journal_issue=0"],
        ["journalIssue", "journal_issue=-4"],
        ["journalIssue", "journal_issue=1.5"],
        ["q", "q=%20%20"],
        ["page", "page=0"],
        ["page", "page=-1"],
        ["page", "page=x"],
        ["page", "page=99999999999"],
    ])("ignores an invalid %s (%s)", (key, query) => {
        const params = parseQueueParams(new URLSearchParams(query));
        expect(params[key as keyof QueueParams]).toEqual(defaults[key as keyof QueueParams]);
    });

    it("ignores an unknown sort", () => {
        expect(parseQueueParams(new URLSearchParams("sort=random")).sort).toBe("score_asc");
    });

    it("keeps the unknown-court marker and trims the search text", () => {
        expect(
            parseQueueParams(new URLSearchParams("court=unknown&q=%20E.%202019%20")),
        ).toMatchObject({
            court: "unknown",
            q: "E. 2019",
        });
    });
});

describe("serializeQueueParams", () => {
    it("leaves out the defaults", () => {
        expect(serializeQueueParams(defaults).toString()).toBe("");
        expect(queueHref(defaults)).toBe("/");
    });

    it("round-trips every parameter", () => {
        const params: QueueParams = {
            band: "high",
            court: "unknown",
            reason: "duplicate_of",
            journalIssue: 12,
            q: "2021/567",
            sort: "score_desc",
            page: 9,
        };
        expect(parseQueueParams(serializeQueueParams(params))).toEqual(params);
    });

    it("builds an href with the query", () => {
        expect(queueHref({ ...defaults, band: "low", page: 2 })).toBe("/?band=low&page=2");
    });
});

describe("changeQueueParams", () => {
    const current: QueueParams = { ...defaults, band: "low", page: 5 };

    it("resets the page when a filter changes", () => {
        expect(changeQueueParams(current, { court: "bam" })).toMatchObject({
            band: "low",
            court: "bam",
            page: 1,
        });
    });

    it("resets the page when the sort changes", () => {
        expect(changeQueueParams(current, { sort: "score_desc" }).page).toBe(1);
    });

    it("clears a filter set to undefined", () => {
        expect(changeQueueParams(current, { band: undefined }).band).toBeUndefined();
    });

    it("keeps the page it is told to go to", () => {
        expect(changeQueueParams(current, { page: 6 })).toMatchObject({ band: "low", page: 6 });
    });
});

describe("activeFilterCount", () => {
    it("is zero for a sort and a page only", () => {
        expect(activeFilterCount({ sort: "score_desc", page: 4 })).toBe(0);
    });

    it("counts each filter that is set", () => {
        expect(activeFilterCount({ ...defaults, band: "low", q: "x" })).toBe(2);
        expect(
            activeFilterCount({
                ...defaults,
                band: "low",
                court: "bam",
                reason: "duplicate_of",
                journalIssue: 3,
                q: "x",
            }),
        ).toBe(5);
    });
});

describe("hasFilters", () => {
    it("ignores sort and page", () => {
        expect(hasFilters({ sort: "score_desc", page: 4 })).toBe(false);
    });

    it.each([
        { band: "low" as const },
        { court: "bam" },
        { reason: "duplicate_of" },
        { journalIssue: 3 },
        { q: "x" },
    ])("is true for %o", (filter) => {
        expect(hasFilters({ ...defaults, ...filter })).toBe(true);
    });
});

describe("apiQuery", () => {
    it("computes the offset from the page", () => {
        expect(apiQuery({ ...defaults, page: 3 })).toMatchObject({ limit: 50, offset: 100 });
    });

    it("sends the unknown court as an empty court", () => {
        expect(apiQuery({ ...defaults, court: "unknown" }).court).toBe("");
        expect(apiQuery({ ...defaults, court: "bam" }).court).toBe("bam");
        expect(apiQuery(defaults).court).toBeUndefined();
    });

    it("maps the journal issue to its API name", () => {
        expect(apiQuery({ ...defaults, journalIssue: 8 }).journal_issue).toBe(8);
    });
});

describe("detail and queue links", () => {
    it("detailHref carries the queue state and the position", () => {
        expect(detailHref("e1", { ...defaults, band: "low", page: 2 }, { pos: 51 })).toBe(
            "/kararlar/e1?band=low&page=2&pos=51",
        );
        expect(detailHref("e1", defaults, { pos: 0, flash: "approved" })).toBe(
            "/kararlar/e1?pos=0&flash=approved",
        );
    });

    it("queueHref carries the notice", () => {
        expect(queueHref(defaults, { flash: "rejected", done: true })).toBe(
            "/?flash=rejected&done=1",
        );
    });

    it("parses the position and the notice, ignoring anything malformed", () => {
        expect(parsePosition({ pos: "0" })).toBe(0);
        expect(parsePosition({ pos: "51" })).toBe(51);
        expect(parsePosition({ pos: "-1" })).toBeUndefined();
        expect(parsePosition({ pos: "x" })).toBeUndefined();
        expect(parsePosition({ pos: "99999999" })).toBeUndefined();
        expect(parsePosition({ pos: "007" })).toBeUndefined();
        expect(parsePosition({ pos: "1.5" })).toBeUndefined();
        expect(parsePosition({ pos: "" })).toBeUndefined();
        expect(parseNotice({ flash: "edited", done: "1" })).toEqual({
            flash: "edited",
            done: true,
        });
        expect(parseNotice({ flash: "<b>" })).toEqual({ flash: undefined, done: false });
    });
});

describe("the status tabs", () => {
    it("reads durum and keeps the queue as the default", () => {
        expect(parseQueueParams(new URLSearchParams("")).status).toBeUndefined();
        expect(parseQueueParams(new URLSearchParams("durum=onaylanan")).status).toBe("approved");
        expect(parseQueueParams(new URLSearchParams("durum=reddedilen")).status).toBe("rejected");
        expect(parseQueueParams(new URLSearchParams("durum=tumu")).status).toBe("all");
        expect(parseQueueParams(new URLSearchParams("durum=bekleyen")).status).toBeUndefined();
        expect(parseQueueParams(new URLSearchParams("durum=bogus")).status).toBeUndefined();
    });

    it("sorts the reviewed tabs by review and the others by score", () => {
        expect(parseQueueParams(new URLSearchParams("durum=onaylanan")).sort).toBe("reviewed_desc");
        expect(parseQueueParams(new URLSearchParams("durum=reddedilen")).sort).toBe(
            "reviewed_desc",
        );
        expect(parseQueueParams(new URLSearchParams("durum=tumu")).sort).toBe("score_asc");
        expect(parseQueueParams(new URLSearchParams("")).sort).toBe("score_asc");
    });

    it("ignores a sort the tab does not offer", () => {
        expect(parseQueueParams(new URLSearchParams("sort=reviewed_desc")).sort).toBe("score_asc");
        expect(sortsFor("pending")).not.toContain("reviewed_desc");
        expect(sortsFor("all")).toContain("reviewed_desc");
        expect(parseQueueParams(new URLSearchParams("durum=tumu&sort=reviewed_desc")).sort).toBe(
            "reviewed_desc",
        );
        expect(parseQueueParams(new URLSearchParams("durum=onaylanan&sort=score_desc")).sort).toBe(
            "score_desc",
        );
    });

    it("leaves out the status and the sort of the tab, and round-trips the rest", () => {
        const rejected: QueueParams = { status: "rejected", sort: "reviewed_desc", page: 1 };
        expect(serializeQueueParams(rejected).toString()).toBe("durum=reddedilen");
        expect(queueHref({ status: "all", sort: "score_asc", page: 1 })).toBe("/?durum=tumu");
        expect(queueHref({ status: "all", sort: "reviewed_desc", page: 2 })).toBe(
            "/?durum=tumu&sort=reviewed_desc&page=2",
        );
        const params: QueueParams = {
            status: "approved",
            band: "low",
            sort: "score_desc",
            page: 3,
        };
        expect(parseQueueParams(serializeQueueParams(params))).toEqual(params);
    });

    it("builds the state of a tab: filters stay, sort and page start over", () => {
        const current: QueueParams = { status: "all", band: "low", sort: "score_desc", page: 4 };
        expect(tabParams(current, "rejected")).toEqual({
            status: "rejected",
            band: "low",
            sort: "reviewed_desc",
            page: 1,
        });
        const queue = tabParams(current, "pending");
        expect(queue.status).toBeUndefined();
        expect(queueHref(queue)).toBe("/?band=low");
    });

    it("sends the tab to the API only when it is not the queue", () => {
        expect(apiQuery({ sort: "score_asc", page: 1 }).status).toBeUndefined();
        expect(apiQuery({ status: "all", sort: "reviewed_desc", page: 2 })).toMatchObject({
            status: "all",
            sort: "reviewed_desc",
            offset: 50,
        });
    });

    it("carries the tab in the detail link, so back and J / K stay in it", () => {
        expect(detailHref("e1", { status: "rejected", sort: "reviewed_desc", page: 1 })).toBe(
            "/kararlar/e1?durum=reddedilen",
        );
    });
});
