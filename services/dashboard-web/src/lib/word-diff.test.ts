import { describe, expect, it } from "vitest";

import { diffWords, hasChanges, type DiffPart } from "./word-diff";

const text = (parts: DiffPart[], kind: DiffPart["kind"]) =>
    parts.filter((p) => p.kind === kind).map((p) => p.text.trim());

describe("diffWords", () => {
    it("finds nothing in equal texts and gives each side back whole", () => {
        const diff = diffWords("İşçi bir ay içinde dava açar.", "İşçi bir ay içinde dava açar.");
        expect(hasChanges(diff)).toBe(false);
        expect(diff.before).toEqual([{ kind: "same", text: "İşçi bir ay içinde dava açar." }]);
        expect(diff.after).toEqual(diff.before);
    });

    it("marks a replaced word on both sides", () => {
        const diff = diffWords(
            "iş mahkemesinde dava açabilir",
            "arabulucuya başvurmak kaydıyla iş mahkemesinde dava açabilir",
        );
        expect(text(diff.before, "removed")).toEqual([]);
        expect(text(diff.after, "added")).toEqual(["arabulucuya başvurmak kaydıyla"]);
        const swapped = diffWords("iki ay içinde", "dört ay içinde");
        expect(text(swapped.before, "removed")).toEqual(["iki"]);
        expect(text(swapped.after, "added")).toEqual(["dört"]);
    });

    it("marks a removal only on the old side", () => {
        const diff = diffWords("a b c d", "a d");
        expect(text(diff.before, "removed")).toEqual(["b c"]);
        expect(diff.after.every((p) => p.kind === "same")).toBe(true);
    });

    it("joins back to the texts on each side", () => {
        const before = "Madde 18 – İşçi\nfesih bildirimi yapılır, yazılı olur.";
        const after = "Madde 18 – İşveren\nfesih bildirimi yapılır; yazılı olur ve gerekçeli.";
        const diff = diffWords(before, after);
        expect(diff.before.map((p) => p.text).join("")).toBe(before);
        expect(diff.after.map((p) => p.text).join("")).toBe(after);
    });

    it("counts punctuation and case as part of the word", () => {
        const diff = diffWords("iş, sözleşmesi", "iş sözleşmesi");
        expect(text(diff.before, "removed")).toEqual(["iş,"]);
        expect(text(diff.after, "added")).toEqual(["iş"]);
    });

    it("does not mind a different whitespace after an unchanged word", () => {
        expect(hasChanges(diffWords("bir iki\nüç", "bir  iki üç"))).toBe(false);
    });

    it("handles empty sides", () => {
        expect(diffWords("", "yeni metin").after).toEqual([{ kind: "added", text: "yeni metin" }]);
        expect(diffWords("eski metin", "").before).toEqual([
            { kind: "removed", text: "eski metin" },
        ]);
        expect(hasChanges(diffWords("", ""))).toBe(false);
    });

    it("is quick on a long article with a few edits and on one with no common word", () => {
        const words = Array.from({ length: 3000 }, (_, i) => `kelime${i}`);
        const edited = [...words.slice(0, 1000), "yeni", ...words.slice(1010)];
        const started = performance.now();
        const diff = diffWords(words.join(" "), edited.join(" "));
        expect(text(diff.after, "added")).toEqual(["yeni"]);
        expect(text(diff.before, "removed")[0]).toContain("kelime1000");
        const unrelated = diffWords(words.join(" "), words.map((w) => `${w}x`).join(" "));
        expect(unrelated.before).toEqual([expect.objectContaining({ kind: "removed" })]);
        expect(performance.now() - started).toBeLessThan(2000);
    });
});
