"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** The heading of a step; it takes the focus when the step appears, so a phase change is announced. */
export function BulkStepHeading({ children }: { children: ReactNode }) {
    const ref = useRef<HTMLHeadingElement>(null);
    useEffect(() => ref.current?.focus(), []);
    return (
        <h3 ref={ref} tabIndex={-1} className="text-sm font-medium text-ink outline-none">
            {children}
        </h3>
    );
}
