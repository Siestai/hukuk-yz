import type * as React from "react";

import { cn } from "../lib/utils";

/** A native `<progress>` (role progressbar); `value` and `max` are in the units the caller counts. */
function Progress({
    className,
    value,
    max,
    ...props
}: Omit<React.ComponentProps<"progress">, "value" | "max"> & { value: number; max: number }) {
    return (
        <progress
            data-slot="progress"
            value={value}
            max={max}
            className={cn(
                "h-2 w-full appearance-none overflow-hidden rounded-sm bg-sunken [&::-webkit-progress-bar]:bg-sunken [&::-webkit-progress-value]:bg-primary [&::-moz-progress-bar]:bg-primary",
                className,
            )}
            {...props}
        />
    );
}

export { Progress };
