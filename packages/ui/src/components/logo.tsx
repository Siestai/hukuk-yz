import type * as React from "react";

type LogoProps = Omit<React.ComponentProps<"svg">, "aria-label"> & { label: string };

/** Scale-of-justice mark, painted with `currentColor`. `label` is the translated accessible name. */
function Logo({ label, ...props }: LogoProps) {
    return (
        <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
            role="img"
            aria-label={label}
            {...props}
        >
            <path d="M12 3v17M7 20h10M5 7h14" />
            <path d="M5 7l-3 7a3 3 0 0 0 6 0L5 7zM19 7l-3 7a3 3 0 0 0 6 0l-3-7z" />
        </svg>
    );
}

export { Logo };
