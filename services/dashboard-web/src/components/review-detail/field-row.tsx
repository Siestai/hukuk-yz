import type { ReactNode } from "react";

/** Values are stored text of any length: they wrap inside the card instead of widening it. */
export function FieldRow({ label, children }: { label: ReactNode; children: ReactNode }) {
    return (
        <div className="grid grid-cols-3 gap-2 border-b border-line-2 py-2 text-sm last:border-b-0">
            <dt className="min-w-0 wrap-anywhere text-ink-3">{label}</dt>
            <dd className="col-span-2 min-w-0 wrap-anywhere text-ink">{children}</dd>
        </div>
    );
}
