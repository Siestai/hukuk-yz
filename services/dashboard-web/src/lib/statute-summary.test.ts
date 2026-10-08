import { describe, expect, it } from "vitest";

import { summarizeStatutes } from "./statute-summary";

const rows = [
    { statute_number: "4857", band: "high", status: "pending", count: 40 },
    { statute_number: "4857", band: "low", status: "pending", count: 3 },
    { statute_number: "4857", band: "high", status: "approved", count: 7 },
    { statute_number: "4857", band: "medium", status: "rejected", count: 2 },
    { statute_number: "5510", band: "medium", status: "pending", count: 11 },
    { statute_number: "9999", band: "high", status: "pending", count: 5 },
] as const;

describe("summarizeStatutes", () => {
    it("counts the statute on screen by band and status", () => {
        expect(summarizeStatutes([...rows], "4857")).toMatchObject({
            bands: { high: 40, medium: 0, low: 3 },
            pending: 43,
            approved: 7,
            rejected: 2,
        });
    });

    it("counts the waiting articles of each reviewed statute for the tabs, ignoring others", () => {
        expect(summarizeStatutes([...rows], "5510")).toMatchObject({
            bands: { high: 0, medium: 11, low: 0 },
            pending: 11,
            waiting: { "4857": 43, "5510": 11 },
        });
    });

    it("is all zeros without rows", () => {
        expect(summarizeStatutes([], "4857")).toEqual({
            bands: { high: 0, medium: 0, low: 0 },
            pending: 0,
            approved: 0,
            rejected: 0,
            waiting: { "4857": 0, "5510": 0 },
        });
    });
});
