import { cva, type VariantProps } from "class-variance-authority";
import type * as React from "react";

import { cn } from "../lib/utils";

const badgeVariants = cva(
    "inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium",
    {
        variants: {
            variant: {
                default: "bg-primary-soft text-primary",
                high: "bg-high-soft text-high",
                medium: "bg-medium-soft text-medium",
                low: "bg-low-soft text-low",
                outline: "border border-border text-ink-2",
            },
        },
        defaultVariants: { variant: "default" },
    },
);

function Badge({
    className,
    variant,
    ...props
}: React.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
    return (
        <span data-slot="badge" className={cn(badgeVariants({ variant }), className)} {...props} />
    );
}

export { Badge, badgeVariants };
