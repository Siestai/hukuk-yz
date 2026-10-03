import { join } from "node:path";

import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const eslint = new ESLint({ cwd: import.meta.dirname });
const uiEslint = new ESLint({
    cwd: join(import.meta.dirname, "../../packages/ui"),
    overrideConfigFile: join(import.meta.dirname, "eslint.config.mjs"),
});

async function ruleIds(code: string, linter = eslint) {
    const [result] = await linter.lintText(code, { filePath: "src/fixture.tsx" });
    return result?.messages.map((m) => m.ruleId) ?? [];
}

describe("eslint.config", () => {
    it("accepts translated text and token classes", async () => {
        const code = `export const Page = ({ t }: { t: (k: string) => string }) => <p className="bg-surface text-ink">{t("a")}</p>;`;
        expect(await ruleIds(code)).toEqual([]);
    });

    it("forbids literal user-facing JSX text", async () => {
        expect(await ruleIds(`export const Page = () => <p>Merhaba</p>;`)).toContain(
            "i18next/no-literal-string",
        );
    });

    it.each([
        ["hex color", `export const Page = () => <p className="text-[#123456]" />;`],
        ["hex color in a style value", `export const c = "#0b2a5b";`],
        ["rgb color", `export const c = "rgba(0, 0, 0, 0.5)";`],
        ["arbitrary tailwind value", `export const c = \`p-[13px] \${1}\`;`],
        [
            "arbitrary tailwind value in className",
            `export const Page = () => <p className="p-[13px]" />;`,
        ],
    ])("forbids a %s", async (_name, code) => {
        expect(await ruleIds(code)).toContain("no-restricted-syntax");
    });

    it.each(["prisma", "@prisma/client", "drizzle-orm", "pg", "postgres", "kysely"])(
        "forbids importing %s",
        async (name) => {
            expect(await ruleIds(`import db from "${name}";\nexport default db;`)).toContain(
                "no-restricted-imports",
            );
        },
    );

    it("applies to packages/ui sources too", async () => {
        const code = `export const Page = () => <p className="p-[13px]" />;`;
        expect(await ruleIds(code, uiEslint)).toContain("no-restricted-syntax");
    });
});
