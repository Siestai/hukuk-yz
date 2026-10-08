export type DiffKind = "same" | "added" | "removed";
export type DiffPart = { kind: DiffKind; text: string };
/** The two texts side by side: `before` holds the same and the removed words, `after` the same and the added. */
export type WordDiff = { before: DiffPart[]; after: DiffPart[] };

/** The longest middle part the table is built for; past it the middle is shown as replaced as a whole. */
const MAX_CELLS = 4_000_000;

/** A word with the whitespace around it, so joining the tokens gives the text back. */
function tokens(text: string): string[] {
    return text.match(/\s*\S+\s*/g) ?? [];
}

const key = (token: string) => token.trim();

function push(parts: DiffPart[], kind: DiffKind, text: string) {
    const last = parts.at(-1);
    if (last?.kind === kind) last.text += text;
    else parts.push({ kind, text });
}

/**
 * Word-level difference of two texts by the longest common subsequence of their words (case and
 * punctuation count: a legal text that differs by a comma differs). A word is unchanged when it
 * is the same word, whatever whitespace follows it. The common start and end are cut off first,
 * so the usual case, an amendment of a few words, costs next to nothing.
 */
export function diffWords(before: string, after: string): WordDiff {
    const a = tokens(before);
    const b = tokens(after);
    const result: WordDiff = { before: [], after: [] };

    let start = 0;
    while (start < a.length && start < b.length && key(a[start] ?? "") === key(b[start] ?? "")) {
        start += 1;
    }
    let endA = a.length;
    let endB = b.length;
    while (endA > start && endB > start && key(a[endA - 1] ?? "") === key(b[endB - 1] ?? "")) {
        endA -= 1;
        endB -= 1;
    }

    for (let i = 0; i < start; i += 1) {
        push(result.before, "same", a[i] ?? "");
        push(result.after, "same", b[i] ?? "");
    }

    const n = endA - start;
    const m = endB - start;
    if ((n + 1) * (m + 1) > MAX_CELLS) {
        for (let i = start; i < endA; i += 1) push(result.before, "removed", a[i] ?? "");
        for (let j = start; j < endB; j += 1) push(result.after, "added", b[j] ?? "");
    } else {
        // lcs[i][j]: the common length of the words from i of the old and from j of the new middle.
        const width = m + 1;
        const lcs = new Uint32Array((n + 1) * width);
        for (let i = n - 1; i >= 0; i -= 1) {
            for (let j = m - 1; j >= 0; j -= 1) {
                lcs[i * width + j] =
                    key(a[start + i] ?? "") === key(b[start + j] ?? "")
                        ? (lcs[(i + 1) * width + j + 1] ?? 0) + 1
                        : Math.max(lcs[(i + 1) * width + j] ?? 0, lcs[i * width + j + 1] ?? 0);
            }
        }
        let i = 0;
        let j = 0;
        while (i < n || j < m) {
            const x = a[start + i] ?? "";
            const y = b[start + j] ?? "";
            if (i < n && j < m && key(x) === key(y)) {
                push(result.before, "same", x);
                push(result.after, "same", y);
                i += 1;
                j += 1;
            } else if (
                j >= m ||
                (i < n && (lcs[(i + 1) * width + j] ?? 0) >= (lcs[i * width + j + 1] ?? 0))
            ) {
                push(result.before, "removed", x);
                i += 1;
            } else {
                push(result.after, "added", y);
                j += 1;
            }
        }
    }

    for (let i = endA; i < a.length; i += 1) push(result.before, "same", a[i] ?? "");
    for (let j = endB; j < b.length; j += 1) push(result.after, "same", b[j] ?? "");
    return result;
}

/** Whether the two texts differ in any word. */
export function hasChanges({ before, after }: WordDiff): boolean {
    return [...before, ...after].some((part) => part.kind !== "same");
}
