import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { THEME_COLOR } from "./theme-color";

const css = readFileSync(join(import.meta.dirname, "../app/globals.css"), "utf8");

describe("THEME_COLOR", () => {
    it("is the --bg token of the chat theme, the color of the mobile top bar", () => {
        const bg = /^\s*--bg:\s*(#[0-9a-f]{3,8})\s*;/im.exec(css)?.[1];
        expect(THEME_COLOR.toLowerCase()).toBe(bg?.toLowerCase());
    });
});
