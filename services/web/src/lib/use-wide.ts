import { useSyncExternalStore } from "react";

const QUERY = "(min-width: 1024px)";

function subscribe(onChange: () => void) {
    const wide = window.matchMedia(QUERY);
    wide.addEventListener("change", onChange);
    return () => wide.removeEventListener("change", onChange);
}

/** True from the `lg` breakpoint: the screen has room for the side columns. False on the server. */
export function useWide(): boolean {
    return useSyncExternalStore(
        subscribe,
        () => window.matchMedia(QUERY).matches,
        () => false,
    );
}
