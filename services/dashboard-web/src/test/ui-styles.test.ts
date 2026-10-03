import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const ROOT = join(import.meta.dirname, "../../../..");
const css = readFileSync(join(ROOT, "packages/ui/src/styles.css"), "utf8");
const design = readFileSync(join(ROOT, "docs/design/dashboard-v0.md"), "utf8");

/** Rows of the token table: `| \`--a\` / \`--b\` | #111 / #222 | ... |` → [["--a", "#111"], ["--b", "#222"]]. */
function designTokens(): [string, string][] {
    return design.split("\n").flatMap((line) => {
        const [, names, values] = line.split("|");
        if (!names || !values || !names.includes("`--")) return [];
        const nameList = [...names.matchAll(/`(--[a-z0-9-]+)`/g)].map((m) => String(m[1]));
        const valueList = values
            .replaceAll("`", "")
            .split("/")
            .map((v) => v.trim());
        return nameList.map((name, i): [string, string] => [name, String(valueList[i])]);
    });
}

describe("packages/ui styles.css", () => {
    const tokens = designTokens();

    it("reads the whole token table from the design doc", () => {
        expect(tokens).toHaveLength(21);
    });

    it.each(tokens)("defines %s as %s", (name, value) => {
        const declaration = new RegExp(`^\\s*${name}:\\s*${value}\\s*;`, "im");
        expect(css).toMatch(declaration);
    });
});
