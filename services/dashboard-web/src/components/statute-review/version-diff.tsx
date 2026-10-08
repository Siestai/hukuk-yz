import { useTranslations } from "next-intl";
import { useMemo } from "react";

import type { TimelineVersion } from "@/lib/statute-as-of";
import { diffWords, hasChanges, type DiffPart } from "@/lib/word-diff";
import { useRange } from "./use-range";

function Side({ title, parts }: { title: string; parts: DiffPart[] | string }) {
    return (
        <div className="grid min-w-0 content-start gap-1">
            <h4 className="text-xs font-medium text-ink-2">{title}</h4>
            <p className="rounded-md border border-border bg-surface-2 p-3 text-sm leading-relaxed wrap-anywhere whitespace-pre-line text-ink">
                {typeof parts === "string"
                    ? parts
                    : parts.map((part, index) =>
                          part.kind === "same" ? (
                              part.text
                          ) : part.kind === "added" ? (
                              <ins
                                  key={index}
                                  className="bg-high-soft text-high underline decoration-1"
                              >
                                  {part.text}
                              </ins>
                          ) : (
                              <del key={index} className="bg-low-soft text-low line-through">
                                  {part.text}
                              </del>
                          ),
                      )}
            </p>
        </div>
    );
}

/**
 * The word-level difference to the version before it: the previous text on the left with what
 * was removed marked, this one on the right with what was added marked; stacked on a phone.
 * Computed here, in the browser, from the two texts the timeline already holds.
 */
export function VersionDiff({
    version,
    previous,
    gapBetween,
}: {
    version: TimelineVersion;
    previous: TimelineVersion | null;
    /** Text is unknown between the two versions: the difference spans a gap. */
    gapBetween: boolean;
}) {
    const t = useTranslations("review.statutes.diff");
    const range = useRange();
    const diff = useMemo(
        () => (previous ? diffWords(previous.text, version.text) : null),
        [previous, version.text],
    );

    if (!previous || !diff) return <p className="text-sm text-ink-2">{t("first")}</p>;
    const sides = diff.tooLong
        ? { before: previous.text, after: version.text }
        : { before: diff.before, after: diff.after };
    return (
        <div className="grid gap-3">
            {gapBetween ? <p className="text-sm text-ink-2">{t("gapBetween")}</p> : null}
            {diff.tooLong ? <p className="text-sm text-ink-2">{t("tooLong")}</p> : null}
            {diff.tooLong || hasChanges(diff) ? (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                    <Side
                        title={t("before", {
                            range: range(previous.valid_from, previous.valid_to),
                        })}
                        parts={sides.before}
                    />
                    <Side
                        title={t("after", { range: range(version.valid_from, version.valid_to) })}
                        parts={sides.after}
                    />
                </div>
            ) : (
                <p className="text-sm text-ink-2">{t("same")}</p>
            )}
            {diff.tooLong ? null : <p className="text-xs text-ink-3">{t("legend")}</p>}
        </div>
    );
}
