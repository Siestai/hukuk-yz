"use client";

import {
    useEffect,
    useId,
    useRef,
    type ComponentProps,
    type ReactNode,
    type RefObject,
} from "react";

import { cn } from "../lib/utils";

type DialogProps = Omit<ComponentProps<"dialog">, "open" | "onClose" | "onCancel" | "title"> & {
    open: boolean;
    /** Called when the dialog asks to close (Escape); the owner sets `open` to false. */
    onClose: () => void;
    title: ReactNode;
    /** Escape closes the dialog unless this is false (a request is in flight). */
    dismissible?: boolean;
    /** Where the focus goes on close; by default the element that had it when the dialog opened. */
    returnFocusTo?: RefObject<HTMLElement | null>;
};

/**
 * Native modal `<dialog>`: `showModal` makes the rest of the page inert, which traps focus.
 * Escape is not left to the browser: it asks the owner to close through `onClose`, and the dialog
 * closes when `open` turns false. Focus then goes to `returnFocusTo`, or else back to the element
 * that had it when the dialog opened (which is the page itself when a keyboard shortcut opened
 * it). The content is mounted only while open, so a form inside starts fresh every time.
 */
function Dialog({
    open,
    onClose,
    title,
    dismissible = true,
    returnFocusTo,
    children,
    className,
    ...props
}: DialogProps) {
    const ref = useRef<HTMLDialogElement>(null);
    const titleId = useId();

    useEffect(() => {
        const dialog = ref.current;
        if (!open || !dialog) return;
        const opener =
            document.activeElement instanceof HTMLElement ? document.activeElement : null;
        const restore = returnFocusTo?.current ?? opener;
        dialog.showModal();
        return () => {
            if (dialog.open) dialog.close();
            restore?.focus();
        };
    }, [open, returnFocusTo]);

    return (
        <dialog
            ref={ref}
            data-slot="dialog"
            aria-labelledby={titleId}
            onCancel={(event) => {
                event.preventDefault();
                if (dismissible) onClose();
            }}
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
