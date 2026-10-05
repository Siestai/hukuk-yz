import type * as React from "react";

import { cn } from "../lib/utils";

/**
 * The button row of a dialog or form: full-width buttons stacked with the main action on top on a
 * phone (the last child, which is also last in the tab order), one right-aligned row from `md` up.
 */
function DialogActions({ className, ...props }: React.ComponentProps<"div">) {
    return (
        <div
            data-slot="dialog-actions"
            className={cn(
                "flex flex-col-reverse gap-2 *:w-full md:flex-row md:justify-end md:*:w-auto",
                className,
            )}
            {...props}
        />
    );
}

export { DialogActions };
