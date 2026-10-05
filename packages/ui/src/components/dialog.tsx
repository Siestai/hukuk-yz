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
import { Button } from "./button";

type DialogProps = Omit<ComponentProps<"dialog">, "open" | "onClose" | "onCancel" | "title"> & {
    open: boolean;
    /** Called when the dialog asks to close (Escape); the owner sets `open` to false. */
    onClose: () => void;
    title: ReactNode;
    /** Escape closes the dialog unless this is false (a request is in flight). */
    dismissible?: boolean;
    /** Where the focus goes on close; by default the element that had it when the dialog opened. */
    returnFocusTo?: RefObject<HTMLElement | null>;
    /** `drawer` slides in from the left edge at full height (the mobile navigation). */
    variant?: "center" | "drawer";
    /** The accessible name of a close button beside the title; without it there is no button. */
    closeLabel?: string;
};

const variantClass = {
    center: "m-auto w-inset max-w-lg max-h-inset rounded-md border",
    drawer: "m-0 mr-auto h-viewport max-h-none w-72 max-w-full rounded-none border-y-0 border-l-0",
} as const;

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
    variant = "center",
    closeLabel,
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
                "overflow-y-auto overscroll-contain border-border bg-surface p-4 text-ink backdrop:bg-ink/40 md:p-5",
                variantClass[variant],
                className,
            )}
            {...props}
        >
            {open ? (
                <div
                    className={cn("grid gap-4", variant === "drawer" && "min-h-full content-start")}
                >
                    <div className="flex items-center justify-between gap-2">
                        <h2 id={titleId} className="font-semibold text-ink">
                            {title}
                        </h2>
                        {closeLabel && dismissible ? (
                            <Button
                                type="button"
                                variant="ghost"
                                size="icon"
                                aria-label={closeLabel}
                                onClick={onClose}
                            >
                                <span aria-hidden="true">×</span>
                            </Button>
                        ) : null}
                    </div>
                    {children}
                </div>
            ) : null}
        </dialog>
    );
}

export { Dialog };
export type { DialogProps };
