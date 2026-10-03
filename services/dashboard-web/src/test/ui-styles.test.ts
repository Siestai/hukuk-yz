import { readFileSync } from "node:fs";
import { join } from "node:path";
import { compile } from "@tailwindcss/node";
import { beforeAll, describe, expect, it } from "vitest";

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

describe("Tailwind output for packages/ui styles", () => {
    const colorTokens = [...css.matchAll(/^\s*--color-([a-z0-9-]+):/gm)].map((m) => String(m[1]));
    let build: (candidates: string[]) => string;

    beforeAll(async () => {
        const compiler = await compile('@import "tailwindcss";\n@import "@hukuk/ui/styles.css";', {
            base: join(ROOT, "services/dashboard-web/src/app"),
            onDependency: () => {},
        });
        build = (candidates) => compiler.build(candidates);
    });

    it("reads the color tokens from the stylesheet", () => {
        expect(colorTokens).toContain("surface");
        expect(colorTokens).toContain("high-soft");
        expect(colorTokens).not.toContain("*");
    });

    it("generates utilities for every color token", () => {
        const candidates = colorTokens.flatMap((name) => [
            `bg-${name}`,
            `text-${name}`,
            `border-${name}`,
        ]);
        const output = build(candidates);
        for (const candidate of candidates) {
            expect(output, candidate).toContain(`.${candidate} {`);
        }
    });

    it.each(["rounded-sm", "rounded-md", "h-row"])("generates %s", (candidate) => {
        expect(build([candidate])).toContain(`.${candidate} {`);
    });

    it.each([
        "bg-red-500",
        "text-blue-600",
        "border-gray-200",
        "bg-white",
        "rounded-lg",
        "rounded-xl",
    ])("does not generate the default %s", (candidate) => {
        expect(build([candidate])).not.toContain(`.${candidate}`);
    });

    it("keeps transparent and current color utilities", () => {
        const output = build(["bg-transparent", "text-current"]);
        expect(output).toContain(".bg-transparent {");
        expect(output).toContain(".text-current {");
    });
});
