import type { ReactNode } from "react";

/**
 * Values are stored text of any length: they wrap inside the card instead of widening it. The label
 * sits above its value on a phone and in a third of the row from `md` up.
 */
export function FieldRow({ label, children }: { label: ReactNode; children: ReactNode }) {
    return (
        <div className="grid gap-1 border-b border-line-2 py-2 text-sm last:border-b-0 md:grid-cols-3 md:gap-2">
            <dt className="min-w-0 wrap-anywhere text-ink-3">{label}</dt>
            <dd className="min-w-0 wrap-anywhere text-ink md:col-span-2">{children}</dd>
        </div>
    );
}
