import { describe, expect, it } from "vitest";

import { pageItems } from "./pagination";

describe("pageItems", () => {
    it("lists every page of a short range", () => {
        expect(pageItems(1, 1)).toEqual([1]);
        expect(pageItems(2, 4)).toEqual([1, 2, 3, 4]);
    });

    it("puts an ellipsis after the first pages", () => {
        expect(pageItems(1, 127)).toEqual([1, 2, "gap", 127]);
    });

    it("puts ellipses on both sides of a page in the middle", () => {
        expect(pageItems(50, 127)).toEqual([1, "gap", 49, 50, 51, "gap", 127]);
    });

    it("puts an ellipsis before the last pages", () => {
        expect(pageItems(127, 127)).toEqual([1, "gap", 126, 127]);
    });

    it("shows a single missing page instead of an ellipsis", () => {
        expect(pageItems(4, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
        expect(pageItems(5, 9)).toEqual([1, "gap", 4, 5, 6, "gap", 9]);
    });

    it("ignores a current page past the end", () => {
        expect(pageItems(9, 3)).toEqual([1, 2, 3]);
    });
});
