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

/** Only the lint guards under test: fixtures are snippets, so unused-variable and undefined-JSX noise is ignored. */
async function guardRuleIds(code: string) {
    const ids = await ruleIds(code);
    return ids.filter((id) => id === "no-restricted-syntax" || id?.startsWith("i18next/"));
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
        ["hex color in a style value", `export const c = "color: #0b2a5b";`],
        ["hex color alone", `export const c = "#0b2a5b";`],
        ["short hex color alone", `export const c = "#fff";`],
        ["hex color in a border shorthand", `export const c = "1px solid #ddd";`],
        ["hex color in a function", `export const c = "linear-gradient(#fff, #000)";`],
        ["rgb color", `export const c = "rgba(0, 0, 0, 0.5)";`],
        ["hsl color", `export const c = "hsl(210 40% 90%)";`],
        ["hsla color", `export const c = "hsla(210, 40%, 90%, 0.5)";`],
        ["oklch color", `export const c = "oklch(0.7 0.1 200)";`],
        ["oklab color", `export const c = "oklab(0.7 0.1 0.1)";`],
        ["hwb color", `export const c = "hwb(210 10% 10%)";`],
        ["lab color", `export const c = "lab(60% 20 20)";`],
        ["lch color", `export const c = "lch(60% 30 200)";`],
        ["color-mix color", `export const c = "color-mix(in srgb, red 40%, blue)";`],
        ["arbitrary tailwind value", `export const c = \`p-[13px] \${1}\`;`],
        [
            "arbitrary tailwind value in className",
            `export const Page = () => <p className="p-[13px]" />;`,
        ],
        ["arbitrary length", `export const c = "w-[42rem]";`],
        ["arbitrary color", `export const c = "bg-[#123]";`],
        ["arbitrary value after a variant", `export const c = "hover:p-[13px]";`],
        ["arbitrary value with an opacity", `export const c = "bg-primary/[.35]";`],
        ["arbitrary value after a nested variant", `export const c = "has-[[data-x]]:p-[3px]";`],
        ["inline style", `export const Page = () => <p style={{ margin: 0 }} />;`],
    ])("forbids a %s", async (_name, code) => {
        expect(await ruleIds(code)).toContain("no-restricted-syntax");
    });

    it.each([
        ["an anchor href", `export const Page = () => <a href="#decade" />;`],
        ["a short anchor href", `export const Page = () => <a href="#add" />;`],
        ["an id", `export const Page = () => <p id="#bad" />;`],
        ["prose with a hash", `export const c = "see #add";`],
        ["a token variable", `export const c = "bg-[var(--surface)] text-[length:var(--size)]";`],
        ["has-[] variants", `export const c = "has-[:checked]:bg-surface has-[>svg]:px-2";`],
        ["data-[] variants", `export const c = "data-[state=open]:bg-surface";`],
        ["aria-[] variants", `export const c = "aria-[invalid=true]:border-low";`],
        ["group variants", `export const c = "group-has-[a]:p-2 group-data-[x=y]/item:p-2";`],
        ["peer variants", `export const c = "peer-data-[x=y]:p-2 peer-has-[:checked]/box:p-2";`],
        ["supports-[] variants", `export const c = "supports-[display:grid]:grid";`],
        ["min-[] and max-[] variants", `export const c = "min-[400px]:p-2 max-[600px]:p-2";`],
        ["nth-[] variants", `export const c = "nth-[3n+1]:bg-surface";`],
        ["selector variants", `export const c = "[&>svg]:size-4 [&_p]:mt-2";`],
        ["nested brackets in a variant", `export const c = "has-[[data-x]]:p-2";`],
        ["array indexing", `export const c = items[0] + "a";\nconst items = ["x"];`],
    ])("allows %s", async (_name, code) => {
        expect(await ruleIds(code)).toEqual([]);
    });

    it.each([
        ["placeholder", `<input placeholder="Ara" />`],
        ["aria-label", `<button aria-label="Kapat" />`],
        ["aria-description", `<button aria-description="Pencereyi kapatır" />`],
        ["title", `<button title="Kapat" />`],
        ["alt", `<img alt="Logo" src={src} />`],
        ["label", `<Field label="Ad" />`],
        ["placeholder expression", `<input placeholder={"Ara"} />`],
        ["title template", "<button title={`Kapat ${x}`} />"],
        ["label conditional", `<Field label={x ? "Ad" : t("a")} />`],
        ["string child", `<p>{"Merhaba"}</p>`],
        ["template child", "<p>{`Merhaba ${x}`}</p>"],
        ["conditional child", `<p>{x ? "Evet" : "Hayır"}</p>`],
        ["logical child", `<p>{x && "Merhaba"}</p>`],
        ["fragment child", `<>{"Merhaba"}</>`],
    ])("forbids a literal %s", async (_name, jsx) => {
        const code = `export declare const x: boolean;\nexport declare const src: string;\nexport const Page = () => ${jsx};`;
        expect(await ruleIds(code)).toContain("no-restricted-syntax");
    });

    it.each([
        ["className", `<p className="flex" />`],
        ["id", `<p id="main" />`],
        ["type", `<input type="text" />`],
        ["href", `<a href="/inceleme" />`],
        ["role", `<p role="status" />`],
        ["key", `<p key="a" />`],
        ["name", `<input name="email" />`],
        ["data-*", `<p data-slot="card" />`],
        ["htmlFor", `<label htmlFor="email" />`],
        ["variant", `<Badge variant="high" />`],
        ["size", `<Button size="sm" />`],
        ["autoComplete", `<input autoComplete="email" />`],
        ["rel", `<a rel="noreferrer" />`],
        ["target", `<a target="_blank" />`],
        ["method", `<form method="post" />`],
        [
            "translated attributes",
            `<input placeholder={t("a")} aria-label={t("b")} title={t("c")} />`,
        ],
        ["translated child", `<p>{t("a")}</p>`],
        ["whitespace child", `<p>{" "}</p>`],
        ["symbol child", `<p>{"—"}</p>`],
        ["interpolation only", "<p>{`${x}`}</p>"],
        ["number child", `<p>{x ? 1 : 2}</p>`],
    ])("allows the technical %s", async (_name, jsx) => {
        const code = `const x = true;\nconst t = (key: string) => key;\nexport const Page = () => ${jsx};`;
        expect(await guardRuleIds(code)).toEqual([]);
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
