"use client";

import { useEffect, useId, useRef, type ComponentProps, type ReactNode } from "react";

import { cn } from "../lib/utils";

type DialogProps = Omit<ComponentProps<"dialog">, "open" | "onClose" | "title"> & {
    open: boolean;
    /** Called when the dialog asks to close (Escape); the owner sets `open` to false. */
    onClose: () => void;
    title: ReactNode;
};

/**
 * Native modal `<dialog>`: `showModal` makes the rest of the page inert, which traps focus, and
 * Escape closes it. Focus goes back to the element that opened it. The content is mounted only
 * while open, so a form inside starts fresh every time.
 */
function Dialog({ open, onClose, title, children, className, ...props }: DialogProps) {
    const ref = useRef<HTMLDialogElement>(null);
    const titleId = useId();

    useEffect(() => {
        const dialog = ref.current;
        if (!open || !dialog) return;
        const opener =
            document.activeElement instanceof HTMLElement ? document.activeElement : null;
        dialog.showModal();
        return () => {
            if (dialog.open) dialog.close();
            opener?.focus();
        };
    }, [open]);

    return (
        <dialog
            ref={ref}
            data-slot="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            onClose={onClose}
            className={cn(
                "m-auto w-full max-w-lg rounded-md border border-border bg-surface p-5 text-ink backdrop:bg-ink/40",
                className,
            )}
            {...props}
        >
            {open ? (
                <div className="grid gap-4">
                    <h2 id={titleId} className="font-semibold text-ink">
                        {title}
                    </h2>
                    {children}
                </div>
            ) : null}
        </dialog>
    );
}

export { Dialog };
export type { DialogProps };
