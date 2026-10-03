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
