import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";

const SRC = join(import.meta.dirname, "..");

function sourceFiles(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) return name === "test" ? [] : sourceFiles(path);
        return /\.(ts|tsx)$/.test(name) && !/\.test\.|\.d\.ts$/.test(name) ? [path] : [];
    });
}

/** Keys passed to `t("...")`, prefixed with the file's `useTranslations`/`getTranslations` namespace. */
function usedKeys(): Set<string> {
    const keys = new Set<string>();
    for (const file of sourceFiles(SRC)) {
        const code = readFileSync(file, "utf8");
        const namespaces = [
            ...code.matchAll(/(?:useTranslations|getTranslations)\((?:"([^"]+)")?\)/g),
        ];
        if (namespaces.length === 0) continue;
        expect(namespaces, `${file}: use one translator namespace per file`).toHaveLength(1);
        const namespace = namespaces[0]?.[1];
        for (const [, key] of code.matchAll(/\bt\("([^"]+)"[,)]/g)) {
            keys.add(namespace ? `${namespace}.${key}` : String(key));
        }
    }
    return keys;
}

function leafKeys(node: object, prefix = ""): string[] {
    return Object.entries(node).flatMap(([key, value]) =>
        typeof value === "object" ? leafKeys(value, `${prefix}${key}.`) : [`${prefix}${key}`],
    );
}

describe("messages/tr.json", () => {
    const defined = new Set(leafKeys(messages));
    const used = usedKeys();

    it("defines every key used in src", () => {
        expect([...used].filter((key) => !defined.has(key))).toEqual([]);
    });

    it("has no unused keys", () => {
        expect([...defined].filter((key) => !used.has(key))).toEqual([]);
    });
});
