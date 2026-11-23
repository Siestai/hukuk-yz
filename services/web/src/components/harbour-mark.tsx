import { cn } from "@hukuk/ui";

/**
 * The mark of the empty state and of the working state: a thin ring, a turquoise dot and a gold
 * horizon (the entrance of a harbour). While `busy` the ring turns; reduced motion stops it.
 */
export function HarbourMark({ busy = false, className }: { busy?: boolean; className?: string }) {
    return (
        <svg
            viewBox="0 0 56 56"
            aria-hidden="true"
            className={cn("size-14 overflow-visible", className)}
        >
            <circle
                cx="28"
                cy="28"
                r="20"
                strokeWidth="1.5"
                className={cn(
                    "fill-none stroke-navy origin-center transform-fill-box",
                    busy && "animate-spin-slow",
                )}
            />
            <line
                x1="14"
                y1="40"
                x2="42"
                y2="40"
                strokeWidth="1.5"
                strokeLinecap="round"
                className="stroke-accent"
            />
            <circle
                cx="28"
                cy="12"
                r="4"
                className={cn("fill-primary", !busy && "animate-breathe")}
            />
        </svg>
    );
}
