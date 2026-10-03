import type * as React from "react";

import { cn } from "../lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
    return (
        <input
            type={type}
            data-slot="input"
            className={cn(
                "flex h-9 w-full rounded-md border border-input bg-surface px-3 py-1 text-sm text-ink placeholder:text-ink-3 focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive",
                className,
            )}
            {...props}
        />
    );
}

export { Input };
