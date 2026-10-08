"use client";

import { cn } from "@hukuk/ui";
import { useRouter, useSearchParams } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useTransition, type ReactNode } from "react";

import type { QueueParams } from "@/lib/queue-params";
import {
    changeState,
    parseState,
    stateHref,
    stateKey,
    type QueueKind,
    type QueueState,
} from "@/lib/queue-state";

type QueueNavigation<P extends QueueState> = {
    params: P;
    isPending: boolean;
    navigate: (change: Partial<P>, mode?: "push" | "replace") => void;
};

const NavigationContext = createContext<QueueNavigation<QueueState> | null>(null);

/**
 * The queue state in the URL and a way to change it: `push` for discrete choices, `replace` for
 * typing. Changes build on the latest change, not on the URL the router has caught up with, so
 * two quick changes both land; `isPending` is true until the router has shown the last one.
 * `kind` is the queue whose URL it reads: decisions (the default) or statute articles.
 */
export function QueueNavigationProvider({
    kind = "decision",
    children,
}: {
    kind?: QueueKind;
    children: ReactNode;
}) {
    const router = useRouter();
    const params = parseState(kind, useSearchParams());
    const key = stateKey(params);
    const [isPending, startTransition] = useTransition();
    const latest = useRef<QueueState>(params);
    const inFlight = useRef<string[]>([]);

    // A URL we pushed ourselves keeps `latest` ahead of it; any other URL (back button, a link)
    // is the new truth.
    useEffect(() => {
        const at = inFlight.current.indexOf(key);
        if (at >= 0) {
            inFlight.current = inFlight.current.slice(at + 1);
        } else {
            inFlight.current = [];
            latest.current = parseState(kind, new URLSearchParams(key));
        }
    }, [key, kind]);

    function navigate(change: Partial<QueueState>, mode: "push" | "replace" = "push") {
        const next = changeState(latest.current, change);
        const href = stateHref(next);
        if (href === stateHref(latest.current)) return;
        latest.current = next;
        inFlight.current.push(stateKey(next));
        startTransition(() => router[mode](href));
    }

    return (
        <NavigationContext value={{ params, isPending, navigate }}>{children}</NavigationContext>
    );
}

/** The navigation of the enclosing provider; `P` is the state type of its `kind` (decisions by default). */
export function useQueueNavigation<P extends QueueState = QueueParams>(): QueueNavigation<P> {
    const navigation = useContext(NavigationContext);
    if (!navigation) throw new Error("useQueueNavigation needs a QueueNavigationProvider");
    return navigation as unknown as QueueNavigation<P>;
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
