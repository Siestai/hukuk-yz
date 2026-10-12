import Link from "next/link";
import { useTranslations } from "next-intl";
import { useId } from "react";

import type { FileMatches } from "@/lib/file-suggestions";
import { fileHref } from "@/lib/files";
import { useEnumLabels } from "@/lib/use-enum-labels";

const linkClass =
    "inline-flex items-center font-medium text-primary underline pointer-coarse:min-h-11";

/**
 * What the new file may be a copy or the next version of: the file it may replace, with the choice
 * to link it or keep it a document of its own, and the files it looks like. The files open in a new
 * tab so they can be compared with this one without losing the form.
 */
export function ApprovalMatches({
    matches,
    names,
    linked,
    onLinkedChange,
}: {
    matches: FileMatches;
    /** Names of the matched files by id; a file without one is shown as unnamed. */
    names: Record<string, string>;
    linked: boolean;
    onLinkedChange: (linked: boolean) => void;
}) {
    const t = useTranslations("files.detail.approve.matches");
    const labels = useEnumLabels();
    const group = useId();
    const name = (id: string) => names[id] ?? t("unnamed");
    const { previous, similar } = matches;
    if (!previous && similar.length === 0) return null;

    return (
        <div className="grid gap-4 rounded-md border border-border bg-surface-2 p-4 text-sm">
            {previous ? (
                <fieldset className="grid gap-2">
                    <legend className="mb-1 text-ink">
                        {t("previous", {
                            name: name(previous.fileId),
                            reason: labels.matchReason(previous.reason),
                        })}
                    </legend>
                    <Link
                        href={fileHref(previous.fileId)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className={linkClass}
                    >
                        {name(previous.fileId)}
                        <span className="sr-only"> ({t("newTab")})</span>
                    </Link>
                    {[true, false].map((value) => (
                        <label
                            key={String(value)}
                            className="flex items-center gap-2 text-ink pointer-coarse:min-h-11"
                        >
                            <input
                                type="radio"
                                name={group}
                                checked={linked === value}
                                onChange={() => onLinkedChange(value)}
                            />
                            {value ? t("link") : t("separate")}
                        </label>
                    ))}
                </fieldset>
            ) : null}
            {similar.length > 0 ? (
                <div className="grid gap-1">
                    <p className="text-ink">{t("similar")}</p>
                    <ul className="grid gap-1">
                        {similar.map((entry) => (
                            <li key={entry.fileId}>
                                <Link
                                    href={fileHref(entry.fileId)}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className={linkClass}
                                >
                                    {t("similarItem", {
                                        name: name(entry.fileId),
                                        score: entry.score,
                                    })}
                                    <span className="sr-only"> ({t("newTab")})</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
        </div>
    );
}
