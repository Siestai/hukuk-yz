import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "@radix-ui/react-slot";
import type * as React from "react";

import { cn } from "../lib/utils";

const buttonVariants = cva(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:pointer-events-none disabled:opacity-50",
    {
        variants: {
            variant: {
                default: "lip lip-primary bg-primary text-primary-foreground hover:bg-primary/90",
                destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
                outline:
                    "lip lip-line border border-input bg-surface text-ink hover:bg-primary-soft",
                secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
                ghost: "text-ink hover:bg-primary-soft",
                // On a navy surface (the chat sidebar).
                inverse: "border border-navy-2 text-ink-inv hover:bg-navy-2",
            },
            size: {
                default: "h-9 px-4 py-2 pointer-coarse:h-11",
                sm: "h-8 px-3 pointer-coarse:h-11",
                lg: "h-10 px-6 pointer-coarse:h-11",
                icon: "size-9 pointer-coarse:size-11",
            },
        },
        defaultVariants: { variant: "default", size: "default" },
    },
);

type ButtonProps = React.ComponentProps<"button"> &
    VariantProps<typeof buttonVariants> & { asChild?: boolean };

function Button({ className, variant, size, asChild = false, ...props }: ButtonProps) {
    const Comp = asChild ? Slot : "button";
    return (
        <Comp
            data-slot="button"
            className={cn(buttonVariants({ variant, size }), className)}
            {...props}
        />
    );
}

export { Button, buttonVariants };
