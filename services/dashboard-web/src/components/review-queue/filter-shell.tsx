"use client";

import { Button, cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

/**
 * The filter area of a queue: on a phone the fields sit behind a toggle, open from the start when
 * a filter is active, and opened again when one is applied from elsewhere (so it is seen).
 */
export function FilterShell({ active, children }: { active: number; children: ReactNode }) {
    const t = useTranslations("review.queue.filters");
    const body = useId();
    const [open, setOpen] = useState(() => active > 0);
    const previous = useRef(active);
    useEffect(() => {
        if (active > previous.current) setOpen(true);
        previous.current = active;
    }, [active]);

    return (
        <section aria-label={t("label")} className="grid gap-3">
            <Button
                type="button"
                variant="outline"
                className="justify-between md:hidden"
                aria-expanded={open}
                aria-controls={body}
                onClick={() => setOpen((value) => !value)}
            >
                {active > 0 ? t("toggleActive", { count: active }) : t("toggle")}
                <svg
                    aria-hidden="true"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className={cn("size-4 transition-transform", open && "rotate-180")}
                >
                    <path d="m6 9 6 6 6-6" />
                </svg>
            </Button>
            <div
                id={body}
                className={cn("gap-4 md:flex md:flex-wrap md:items-end", open ? "grid" : "hidden")}
            >
                {children}
            </div>
        </section>
    );
}
