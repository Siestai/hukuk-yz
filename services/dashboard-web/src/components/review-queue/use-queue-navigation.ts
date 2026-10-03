"use client";

import { useRouter, useSearchParams } from "next/navigation";

import {
    changeQueueParams,
    parseQueueParams,
    queueHref,
    type QueueChange,
} from "@/lib/queue-params";

/** The queue state in the URL and a way to change it: `push` for discrete choices, `replace` for typing. */
export function useQueueNavigation() {
    const router = useRouter();
    const params = parseQueueParams(useSearchParams());
    function navigate(change: QueueChange, mode: "push" | "replace" = "push") {
        router[mode](queueHref(changeQueueParams(params, change)));
    }
    return { params, navigate };
}
