"use client";

import * as Popover from "@radix-ui/react-popover";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

import { cn } from "../lib/utils";

/** How long the box stays after the pointer leaves, so it can be crossed onto (WCAG 1.4.13). */
const HOVER_CLOSE_DELAY_MS = 150;

type InfoTipProps = {
    /** The accessible name of the button, for example "Bilgi: Güven dağılımı". */
    label: string;
    /** The explanation: a few short sentences of plain text. */
    children: ReactNode;
    className?: string;
};

const focusVisible = (element: HTMLElement) => {
    try {
        return element.matches(":focus-visible");
    } catch {
        return true;
    }
};

/**
 * A small "i" button with a short explanation, a toggletip. A mouse pointer over it or keyboard
 * focus on it shows the box; a click or tap pins it open (a phone has no hover), and Escape, a
 * tap outside or a second click closes it. Focus stays on the button throughout.
 *
 * For screen readers the explanation is not the visible box (which is `aria-hidden`) but a live
 * region next to the button that is filled when the button is activated, so activating it reads
 * the text out, and merely tabbing past does not. The box is rendered in place, not in a portal:
 * it is `position: fixed` and so is neither clipped by a scrolling table nor left behind the top
 * layer of a modal `<dialog>`.
 */
function InfoTip({ label, children, className }: InfoTipProps) {
    // Three reasons to be open: pinned by a click or tap, the pointer over the button or the box
    // (kept for a moment after it leaves), keyboard focus on the button.
    const [pinned, setPinned] = useState(false);
    const [hover, setHover] = useState(false);
    const [leaving, setLeaving] = useState(false);
    const [focused, setFocused] = useState(false);
    const button = useRef<HTMLButtonElement>(null);
    const contentId = useId();
    const open = pinned || hover || focused;

    useEffect(() => {
        if (!leaving) return;
        const timer = setTimeout(() => {
            setHover(false);
            setLeaving(false);
        }, HOVER_CLOSE_DELAY_MS);
        return () => clearTimeout(timer);
    }, [leaving]);

    const close = () => {
        setPinned(false);
        setHover(false);
        setLeaving(false);
        setFocused(false);
    };
    // A finger is not a hover: a touch opens the box through the click that follows it.
    const pointer = {
        onPointerEnter: (event: { pointerType: string }) => {
            if (event.pointerType === "touch") return;
            setLeaving(false);
            setHover(true);
        },
        onPointerLeave: (event: { pointerType: string }) => {
            if (event.pointerType !== "touch") setLeaving(true);
        },
    };

    return (
        <Popover.Root open={open} onOpenChange={(next) => (next ? undefined : close())}>
            <Popover.Anchor asChild>
                <button
                    ref={button}
                    type="button"
                    data-slot="info-tip"
                    aria-label={label}
                    aria-expanded={open}
                    aria-controls={open ? contentId : undefined}
                    onClick={() => (pinned ? close() : setPinned(true))}
                    onFocus={(event) => setFocused(focusVisible(event.currentTarget))}
                    onBlur={close}
                    {...pointer}
                    className={cn(
                        "inline-flex size-5 shrink-0 items-center justify-center rounded-md text-ink-3 hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring pointer-coarse:-m-3 pointer-coarse:size-11",
                        open && "text-primary",
                        className,
                    )}
                >
                    <svg
                        aria-hidden="true"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        className="size-4"
                    >
                        <circle cx={12} cy={12} r={9} />
                        <path d="M12 11v5" />
                        <path d="M12 8h.01" />
                    </svg>
                </button>
            </Popover.Anchor>
            <span role="status" className="sr-only">
                {pinned ? children : null}
            </span>
            {open ? (
                <Popover.Content
                    id={contentId}
                    data-slot="info-tip-content"
                    aria-hidden="true"
                    side="bottom"
                    align="start"
                    sideOffset={6}
                    collisionPadding={8}
                    onOpenAutoFocus={(event) => event.preventDefault()}
                    onCloseAutoFocus={(event) => event.preventDefault()}
                    // The button is the anchor, not a Popover.Trigger: a press on it is not "outside".
                    onInteractOutside={(event) => {
                        if (
                            event.target instanceof Node &&
                            button.current?.contains(event.target)
                        ) {
                            event.preventDefault();
                        }
                    }}
                    {...pointer}
                    className="z-30 w-72 max-w-available rounded-md border border-border bg-popover p-3 text-left text-sm font-normal text-popover-foreground shadow-md"
                >
                    {children}
                </Popover.Content>
            ) : null}
        </Popover.Root>
    );
}

export { InfoTip };
export type { InfoTipProps };
