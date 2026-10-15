import { useSyncExternalStore } from "react";

/** Tailwind's `md` is 768 px, so a phone is anything narrower. */
const PHONE = "(max-width: 767.98px)";

function subscribe(onChange: () => void): () => void {
    const query = window.matchMedia(PHONE);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
}

/**
 * Whether the screen is narrower than `md`. For what CSS cannot choose: an embedded component that
 * must not even be loaded where it is hidden. Use it only below client-rendered, post-hydration
 * content (a window that is open), as the server cannot know the width.
 */
export function usePhone(): boolean {
    return useSyncExternalStore(
        subscribe,
        () => window.matchMedia(PHONE).matches,
        () => false,
    );
}
