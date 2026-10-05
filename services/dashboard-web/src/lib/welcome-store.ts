import { useSyncExternalStore } from "react";

/** Whether the reviewer has closed the welcome card; kept in the browser only, never sent to the server. */
export const WELCOME_STORAGE_KEY = "libria.queue-welcome";
const DISMISSED = "dismissed";

const listeners = new Set<() => void>();
// Storage can be blocked (private mode, policy): the choice then holds until the page is left.
let fallback = false;

const read = () => {
    try {
        return window.localStorage.getItem(WELCOME_STORAGE_KEY) === DISMISSED || fallback;
    } catch {
        return fallback;
    }
};

export function setWelcomeDismissed(dismissed: boolean) {
    fallback = false;
    try {
        if (dismissed) window.localStorage.setItem(WELCOME_STORAGE_KEY, DISMISSED);
        else window.localStorage.removeItem(WELCOME_STORAGE_KEY);
    } catch {
        fallback = dismissed;
    }
    listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
    listeners.add(listener);
    // Another tab closing the card.
    const onStorage = (event: StorageEvent) => {
        if (event.key === WELCOME_STORAGE_KEY || event.key === null) listener();
    };
    window.addEventListener("storage", onStorage);
    return () => {
        listeners.delete(listener);
        window.removeEventListener("storage", onStorage);
    };
}

/**
 * The server and the first client render both say "dismissed": the card is not in the HTML, so a
 * reviewer who closed it never sees it flash, and hydration matches. A first-time visitor gets
 * the card right after hydration, once, since the stored choice is only readable in the browser.
 */
export function useWelcomeDismissed() {
    return useSyncExternalStore(subscribe, read, () => true);
}
