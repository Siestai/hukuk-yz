"use client";

import { cn } from "@hukuk/ui";
import { useRouter, useSearchParams } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useTransition, type ReactNode } from "react";

import {
    changeQueueParams,
    parseQueueParams,
    queueHref,
    serializeQueueParams,
    type QueueChange,
    type QueueParams,
} from "@/lib/queue-params";

type QueueNavigation = {
    params: QueueParams;
    isPending: boolean;
    navigate: (change: QueueChange, mode?: "push" | "replace") => void;
};

const NavigationContext = createContext<QueueNavigation | null>(null);

/**
 * The queue state in the URL and a way to change it: `push` for discrete choices, `replace` for
 * typing. Changes build on the latest change, not on the URL the router has caught up with, so
 * two quick changes both land; `isPending` is true until the router has shown the last one.
 */
export function QueueNavigationProvider({ children }: { children: ReactNode }) {
    const router = useRouter();
    const params = parseQueueParams(useSearchParams());
    const key = serializeQueueParams(params).toString();
    const [isPending, startTransition] = useTransition();
    const latest = useRef(params);
    const inFlight = useRef<string[]>([]);

    // A URL we pushed ourselves keeps `latest` ahead of it; any other URL (back button, a link)
    // is the new truth.
    useEffect(() => {
        const at = inFlight.current.indexOf(key);
        if (at >= 0) {
            inFlight.current = inFlight.current.slice(at + 1);
        } else {
            inFlight.current = [];
            latest.current = parseQueueParams(new URLSearchParams(key));
        }
    }, [key]);

    function navigate(change: QueueChange, mode: "push" | "replace" = "push") {
        const next = changeQueueParams(latest.current, change);
        const href = queueHref(next);
        if (href === queueHref(latest.current)) return;
        latest.current = next;
        inFlight.current.push(serializeQueueParams(next).toString());
        startTransition(() => router[mode](href));
    }

    return (
        <NavigationContext value={{ params, isPending, navigate }}>{children}</NavigationContext>
    );
}

export function useQueueNavigation(): QueueNavigation {
    const navigation = useContext(NavigationContext);
    if (!navigation) throw new Error("useQueueNavigation needs a QueueNavigationProvider");
    return navigation;
}

/** The results area: busy and dimmed while a filter, sort or search change is on its way. */
export function QueueResultsRegion({ children }: { children: ReactNode }) {
    const { isPending } = useQueueNavigation();
    return (
        <div
            aria-busy={isPending || undefined}
            className={cn("transition-opacity", isPending && "opacity-60")}
        >
            {children}
        </div>
    );
}
