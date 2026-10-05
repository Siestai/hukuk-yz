import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import { BULK_FAILURE_CODES } from "../lib/bulk-approve";
import { HELP_TOPICS } from "../lib/help-topics";
import { FIELD_ERRORS } from "../lib/decision-edits";
import { BANDS, COURTS, FLASHES, SORTS, UNKNOWN_COURT } from "../lib/queue-params";
import {
    readRepoFile,
    reasonCodes,
    schemaEnum,
    schemaProperties,
    warningCodes,
} from "../test/reason-codes";

const SRC = join(import.meta.dirname, "..");

function sourceFiles(dir: string): string[] {
    return readdirSync(dir).flatMap((name) => {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) return name === "test" ? [] : sourceFiles(path);
        return /\.(ts|tsx)$/.test(name) && !/\.test\.|\.d\.ts$/.test(name) ? [path] : [];
    });
}

/**
 * Keys passed to `t("...")`, prefixed with the file's `useTranslations`/`getTranslations` namespace.
 * Keys built at run time (t(`group.${value}`), enum labels) are not seen here; the groups that
 * are built that way are listed in DYNAMIC_GROUPS and checked against their source of values.
 */
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

function leafTexts(node: object): string[] {
    return Object.values(node).flatMap((value) =>
        typeof value === "object" ? leafTexts(value) : [String(value)],
    );
}

function roles(): string[] {
    const schema = readFileSync(join(SRC, "lib/api/schema.d.ts"), "utf8");
    const union = /^\s+role: ((?:"\w+"(?: \| )?)+);/m.exec(schema)?.[1] ?? "";
    return [...union.matchAll(/"(\w+)"/g)].map((m) => String(m[1]));
}

/** Groups whose keys are built at run time, with the values the code can build them from. */
const DYNAMIC_GROUPS: Record<string, readonly string[]> = {
    "enums.band": BANDS,
    "enums.court": [...COURTS, UNKNOWN_COURT],
    "enums.reason": reasonCodes(),
    "enums.warning": warningCodes(),
    "enums.courtLevel": schemaEnum("DecisionEdits", "court_level"),
    "enums.outcome": schemaEnum("DecisionEdits", "outcome"),
    "enums.jurisdiction": schemaEnum("DecisionEdits", "jurisdiction"),
    "enums.textCompleteness": schemaEnum("DecisionEdits", "text_completeness"),
    "enums.bulkFailure": BULK_FAILURE_CODES,
    "enums.sourceStatus": schemaEnum("ReviewDetail", "source_status"),
    // The fields a reviewer may correct, plus the read-only ones the detail screen shows.
    fields: [...schemaProperties("DecisionEdits"), "journal_issue"],
    // "available" shows the frame; the other two values are the empty-state texts.
    "review.detail.pdf": schemaEnum("ReviewDetail", "pdf").filter((v) => v !== "available"),
    "review.detail.history.decision": schemaEnum("ReviewOut", "decision"),
    "review.bulk.run": ["published", "conflicts", "failed"],
    "review.bulk.report.heading": ["finished", "stopped", "failed"],
    "review.queue.help": [...HELP_TOPICS, ...reasonCodes().map((code) => `reason.${code}`)],
    "review.queue.sort": SORTS,
    "review.queue.flash": FLASHES,
    // "server" is read by key; the others are the client checks of the form.
    "review.edit.errors": FIELD_ERRORS,
};

describe("messages/tr.json", () => {
    const defined = new Set(leafKeys(messages));
    const used = usedKeys();
    const dynamic = new Set(
        Object.entries(DYNAMIC_GROUPS).flatMap(([group, values]) =>
            values.map((value) => `${group}.${value}`),
        ),
    );

    it("defines every key used in src", () => {
        expect([...used].filter((key) => !defined.has(key))).toEqual([]);
    });

    it("has no unused keys", () => {
        expect([...defined].filter((key) => !used.has(key) && !dynamic.has(key))).toEqual([]);
    });

    it.each(Object.keys(DYNAMIC_GROUPS))(
        "%s has exactly the keys of its source of values",
        (group) => {
            const values = DYNAMIC_GROUPS[group] ?? [];
            const keys = [...defined]
                .filter((key) => key.startsWith(`${group}.`) && !used.has(key))
                .map((key) => key.slice(group.length + 1));
            expect(keys.sort()).toEqual([...values].sort());
        },
    );

    it("keeps help and welcome texts short and free of the long dash", () => {
        const texts = [
            ...leafTexts(messages.review.queue.help),
            ...leafTexts(messages.review.queue.welcome),
        ];
        for (const text of texts) {
            expect(text).not.toContain("\u2014");
            expect(text.length, text).toBeLessThanOrEqual(480);
        }
    });

    it("states the penalties and bands of the confidence rules in the band tip", () => {
        const source = readRepoFile("services/app/app/loaders/confidence.py");
        const low = /^LOW_PENALTY = (\d+)/m.exec(source)?.[1];
        const medium = /^MEDIUM_PENALTY = (\d+)/m.exec(source)?.[1];
        expect(messages.review.queue.help.band).toContain(`Düşük bantlı sebep ${low},`);
        expect(messages.review.queue.help.band).toContain(`Orta bantlı sebep ${medium})`);
    });

    it("enums.role has exactly the roles of the API (read in side-nav by key)", () => {
        expect(Object.keys(messages.enums.role).sort()).toEqual(roles().sort());
    });
});
