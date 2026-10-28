import type { ReactNode } from "react";

/** A closable section: a row with a title and a short hint, the content below it when open. */
export function FoldSection({
    title,
    hint,
    open = false,
    children,
}: {
    title: ReactNode;
    hint?: ReactNode;
    open?: boolean;
    children: ReactNode;
}) {
    return (
        <details open={open} className="group border-t border-line">
            <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 focus-visible:outline-2 focus-visible:outline-ring [&::-webkit-details-marker]:hidden">
                <span className="font-semibold text-ink">{title}</span>
                <span className="flex items-center gap-1 text-sm text-ink-3">
                    {hint}
                    <svg
                        aria-hidden="true"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        className="size-4 transition-transform group-open:rotate-90"
                    >
                        <path d="M9 6l6 6-6 6" />
                    </svg>
                </span>
            </summary>
            <div className="px-4 pb-4">{children}</div>
        </details>
    );
}
