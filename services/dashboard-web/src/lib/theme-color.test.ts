import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { THEME_COLOR } from "./theme-color";

const css = readFileSync(
    join(import.meta.dirname, "../../../../packages/ui/src/styles.css"),
    "utf8",
);

describe("THEME_COLOR", () => {
    it("is the --surface token, the color of the mobile top bar", () => {
        const surface = /^\s*--surface:\s*(#[0-9a-f]{3,8})\s*;/im.exec(css)?.[1];
        expect(THEME_COLOR.toLowerCase()).toBe(surface?.toLowerCase());
    });
});
