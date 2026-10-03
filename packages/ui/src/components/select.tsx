import type * as React from "react";

import { cn } from "../lib/utils";

/** Native select: keyboard and screen reader support come from the browser. */
function Select({ className, ...props }: React.ComponentProps<"select">) {
    return (
        <select
            data-slot="select"
            className={cn(
                "flex h-9 w-full rounded-md border border-input bg-surface px-3 py-1 text-sm text-ink focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50",
                className,
            )}
            {...props}
        />
    );
}

export { Select };
