import { useEffect, useRef } from "react";

export type Shortcut = "approve" | "edit" | "reject" | "next" | "previous";

/** The key of each shortcut, as the action bar prints it. */
export const SHORTCUT_KEYS: Record<Shortcut, string> = {
    approve: "A",
    edit: "E",
    reject: "R",
    next: "J",
    previous: "K",
};

const EDITABLE = 'input, textarea, select, [contenteditable]:not([contenteditable="false"])';

/** The shortcut a key press asks for, or null when it must be left alone (typing, modifiers, a dialog). */
export function shortcutFor(event: KeyboardEvent): Shortcut | null {
    if (event.defaultPrevented || event.repeat) return null;
    if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return null;
    if (event.target instanceof Element && event.target.closest(EDITABLE)) return null;
    if (document.querySelector("dialog[open]")) return null;
    const key = event.key.toLocaleUpperCase("en");
    return (Object.keys(SHORTCUT_KEYS) as Shortcut[]).find((s) => SHORTCUT_KEYS[s] === key) ?? null;
}

/** Runs the handler of a pressed shortcut; nothing runs while `enabled` is false (a request is on its way). */
export function useReviewShortcuts(handlers: Record<Shortcut, () => void>, enabled: boolean) {
    const latest = useRef(handlers);
    useEffect(() => {
        latest.current = handlers;
    });
    useEffect(() => {
        if (!enabled) return;
        function onKeyDown(event: KeyboardEvent) {
            const shortcut = shortcutFor(event);
            if (!shortcut) return;
            event.preventDefault();
            latest.current[shortcut]();
        }
        document.addEventListener("keydown", onKeyDown);
        return () => document.removeEventListener("keydown", onKeyDown);
    }, [enabled]);
}
