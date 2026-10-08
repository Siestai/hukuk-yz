import { readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = join(import.meta.dirname, "../../../..");

export const readRepoFile = (path: string) => readFileSync(join(ROOT, path), "utf8");

/** Keys of the `RULES` table of the confidence rules: every code a review can carry. */
export function reasonCodes(): string[] {
    const source = readRepoFile("services/app/app/loaders/confidence.py");
    const table = /^RULES[^\n]*= \{\n([\s\S]*?)^\}/m.exec(source)?.[1] ?? "";
    return [...table.matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => String(m[1]));
}

/**
 * Codes of `extraction.warnings`: what the parser (`hukuk_ingest.decisions`) and the loader append
 * (`app.loaders`), without the `:detail` some of them carry.
 */
export function warningCodes(): string[] {
    const sources = [
        "packages/ingest/hukuk_ingest/decisions/fields.py",
        "packages/ingest/hukuk_ingest/decisions/qa.py",
        "packages/ingest/hukuk_ingest/decisions/report.py",
        "services/app/app/loaders/normalize.py",
        "services/app/app/loaders/decisions.py",
    ];
    const codes = sources.flatMap((path) =>
        [...readRepoFile(path).matchAll(/\.append\(f?"([a-z][a-z_]+)["':]/g)].map((m) =>
            String(m[1]),
        ),
    );
    return [...new Set(codes)];
}

type Schemas = Record<string, { properties: Record<string, unknown> }>;

const schemas = () =>
    (
        JSON.parse(readRepoFile("services/dashboard-web/openapi.json")) as {
            components: { schemas: Schemas };
        }
    ).components.schemas;

function firstEnum(node: unknown): string[] {
    if (typeof node !== "object" || node === null) return [];
    const record = node as Record<string, unknown>;
    if (Array.isArray(record.enum)) return record.enum.map(String);
    return Object.values(record).flatMap(firstEnum);
}

/** The enum values of one property of a schema in the committed `openapi.json`. */
export function schemaEnum(schema: string, property: string): string[] {
    return firstEnum(schemas()[schema]?.properties[property]);
}

/** The properties of a schema in the committed `openapi.json`. */
export function schemaProperties(schema: string): string[] {
    return Object.keys(schemas()[schema]?.properties ?? {});
}

const STATUTE_SOURCES = ["split", "timeline", "diff", "run"].map(
    (name) => `packages/ingest/hukuk_ingest/statutes/${name}.py`,
);

/** Keys of the `RULES` table of the statute confidence rules: the codes that lower an article's band. */
export function statuteReasonCodes(): string[] {
    const source = readRepoFile("packages/ingest/hukuk_ingest/statutes/confidence.py");
    const table = /^RULES[^\n]*= \{\n([\s\S]*?)^\}/m.exec(source)?.[1] ?? "";
    return [...table.matchAll(/^\s+"([a-z_]+)":/gm)].map((m) => String(m[1]));
}

/**
 * Codes of the warnings of a statute timeline (`extraction.warnings`) and the reasons of its gaps:
 * the confidence rules plus what the statute code appends, without the `:detail` some carry.
 */
export function statuteWarningCodes(): string[] {
    const appended = STATUTE_SOURCES.flatMap((path) =>
        [...readRepoFile(path).matchAll(/\.append\(f?"([a-z][a-z_]+)["':]/g)].map((m) =>
            String(m[1]),
        ),
    );
    const gapReasons = [
        ...readRepoFile(STATUTE_SOURCES[1] ?? "").matchAll(/_gap\([^)]*"([a-z][a-z_]+)"/g),
    ].map((m) => String(m[1]));
    return [...new Set([...statuteReasonCodes(), ...appended, ...gapReasons])];
}
