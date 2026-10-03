import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { pickQuote } from "./quotes";

const root = join(import.meta.dirname, "../..");
const read = (path: string) => readFileSync(join(root, path), "utf8");

describe("pickQuote", () => {
    it("returns a quote with text and author", async () => {
        const quote = await pickQuote("tr");
        expect(quote.text).not.toBe("");
        expect(quote.author).not.toBe("");
    });

    it("picks by the random value, first and last", async () => {
        const quotes = JSON.parse(read("content/login-quotes.tr.json"));
        expect(await pickQuote("tr", () => 0)).toEqual(quotes[0]);
        expect(await pickQuote("tr", () => 0.999999)).toEqual(quotes.at(-1));
    });

    it("keeps the content copy identical to the design source", () => {
        expect(read("content/login-quotes.tr.json")).toBe(
            read("../../docs/design/login-quotes.tr.json"),
        );
    });
});
