"use client";

import { useRouter } from "next/navigation";
import {
    createContext,
    useContext,
    useEffect,
    useMemo,
    useRef,
    useState,
    useTransition,
    type ReactNode,
} from "react";

import { createApiClient } from "@/lib/api/client";
import {
    ApiFailure,
    locate,
    neighbour,
    nextAfter,
    postReview,
    type ReviewAction,
} from "@/lib/api/review-client";
import type { DecisionEdits } from "@/lib/decision-edits";
import { detailHref, queueHref, type Flash, type QueueParams } from "@/lib/queue-params";

/** How long a screen change may take before the session gives up waiting for it. */
export const NAVIGATION_TIMEOUT_MS = 10_000;

export type Failure = { code?: string; params: Record<string, unknown> };
export type Mode = "view" | "edit";
export type Pending = "approve" | "edit" | "reject" | "move";

type Session = {
    /** Whether the record is in the queue: only then are there actions at all. */
    canAct: boolean;
    mode: Mode;
    /** A request is on its way, or the screen is moving on after one: no other action may start. */
    busy: boolean;
    /** Which request it is, for the button that started it. */
    pending: Pending | null;
    failure: Failure | null;
    /** The queue list in the state this record was opened from. */
    queueHref: string;
    /** A move that found nothing: there is no next / previous record. */
    edge: "next" | "previous" | null;
    startEdit: () => void;
    cancelEdit: () => void;
    /** The actions resolve to whether they went through, so a dialog can close and show the failure. */
    approve: () => Promise<boolean>;
    submitEdit: (edits: DecisionEdits, note: string) => Promise<boolean>;
    reject: (note: string) => Promise<boolean>;
    move: (direction: "next" | "previous") => Promise<void>;
};

const SessionContext = createContext<Session | null>(null);

type Props = {
    extractionId: string;
    queue: QueueParams;
    /** The record's index in the queue, from the link that led here. */
    pos: number | undefined;
    canAct: boolean;
    children: ReactNode;
};

/**
 * The review actions of one record. Before acting, the record's index in the queue is verified
 * (`locate`). After an action the screen moves on to the NEXT pending record of the same queue
 * state: the acted-on record has left the queue, so the record that now sits at its old index is
 * the next one, or the top of the queue if it was the last. Only a queue confirmed empty ends with
 * "queue finished"; if the next record cannot be determined the screen goes back to the list. The
 * page is keyed by record, so the session stays busy after a success until the next screen
 * replaces this one, or until `NAVIGATION_TIMEOUT_MS` has passed.
 */
export function ReviewProvider({ extractionId, queue, pos, canAct, children }: Props) {
    const router = useRouter();
    const api = useMemo(() => createApiClient(), []);
    const [, startTransition] = useTransition();
    const [mode, setMode] = useState<Mode>("view");
    const [pending, setPending] = useState<Pending | null>(null);
    const [failure, setFailure] = useState<Failure | null>(null);
    const [edge, setEdge] = useState<Session["edge"]>(null);
    const running = useRef(false);
    const stalled = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const toQueue = queueHref(queue);

    useEffect(() => () => clearTimeout(stalled.current), []);

    function release(next: Failure | null = null) {
        running.current = false;
        setPending(null);
        setFailure(next);
    }

    /** One request at a time; a failure is kept for the screen, a lost session leaves it. */
    async function guarded(kind: Pending, work: () => Promise<void>): Promise<boolean> {
        if (running.current || !canAct) return false;
        running.current = true;
        setPending(kind);
        setFailure(null);
        setEdge(null);
        try {
            await work();
            return true;
        } catch (error) {
            const failed = error instanceof ApiFailure ? error : new ApiFailure(undefined);
            if (failed.code === "unauthorized") {
                startTransition(() => router.push("/oturum-sonu"));
                return false;
            }
            release({ code: failed.code, params: failed.params });
            return false;
        }
    }

    /** Leaves for another screen; if that never completes the actions come back with a way out. */
    function go(href: string) {
        const stuck = () => release({ code: "navigation_failed", params: {} });
        clearTimeout(stalled.current);
        stalled.current = setTimeout(stuck, NAVIGATION_TIMEOUT_MS);
        // React reports an error thrown inside a transition instead of passing it on, so it is caught there.
        startTransition(() => {
            try {
                router.push(href);
            } catch {
                clearTimeout(stalled.current);
                stuck();
            }
        });
    }

    function act(kind: Pending, body: ReviewAction, flash: Flash) {
        return guarded(kind, async () => {
            // Verified before the record leaves the queue; without it there is no "next" to compute.
            const at = await locate(api, queue, extractionId, pos).catch(() => null);
            await postReview(api, extractionId, body);
            // The action went through: a failed lookup from here on must not pass as "finished".
            const next =
                at === null ? undefined : await nextAfter(api, queue, at).catch(() => undefined);
            if (next === undefined) go(queueHref(queue, { flash }));
            else if (next === null) go(queueHref(queue, { flash, done: true }));
            else go(detailHref(next.id, queue, { pos: next.pos, flash }));
        });
    }

    const session: Session = {
        canAct,
        mode,
        busy: pending !== null,
        pending,
        failure,
        queueHref: toQueue,
        edge,
        startEdit: () => {
            if (canAct && !running.current) setMode("edit");
        },
        cancelEdit: () => {
            setMode("view");
            setFailure(null);
        },
        approve: () => act("approve", { action: "approve" }, "approved"),
        submitEdit: (edits, note) =>
            act("edit", { action: "edit", edits, note: note.trim() || undefined }, "edited"),
        reject: (note) => act("reject", { action: "reject", note: note.trim() }, "rejected"),
        move: async (direction) => {
            await guarded("move", async () => {
                const found = await neighbour(
                    api,
                    queue,
                    extractionId,
                    pos,
                    direction === "next" ? 1 : -1,
                );
                if (found.kind === "edge") {
                    setEdge(direction);
                    release();
                } else {
                    go(
                        found.kind === "record"
                            ? detailHref(found.id, queue, { pos: found.pos })
                            : toQueue,
                    );
                }
            });
        },
    };

    return <SessionContext value={session}>{children}</SessionContext>;
}

export function useReviewSession(): Session {
    const session = useContext(SessionContext);
    if (!session) throw new Error("useReviewSession needs a ReviewProvider");
    return session;
}
