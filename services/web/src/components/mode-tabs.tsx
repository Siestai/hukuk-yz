"use client";

import { cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { ChatMode } from "@/lib/chat-types";

const MODES: readonly ChatMode[] = ["short", "detailed", "reasoned"];

/** The fixed mode selector: the same answer, shown shorter or longer. It sends no request. */
export function ModeTabs({
    mode,
    onChange,
    className,
}: {
    mode: ChatMode;
    onChange: (mode: ChatMode) => void;
    className?: string;
}) {
    const t = useTranslations("chat.mode");
    return (
        <div
            role="tablist"
            aria-label={t("label")}
            className={cn("grid grid-cols-3 gap-1 rounded-md bg-sunken p-1", className)}
        >
            {MODES.map((value) => (
                <button
                    key={value}
                    type="button"
                    role="tab"
                    aria-selected={mode === value}
                    onClick={() => onChange(value)}
                    className={cn(
                        "min-h-9 rounded-md px-3 text-sm font-medium focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:min-h-11",
                        mode === value ? "bg-surface text-primary shadow-sm" : "text-ink-2",
                    )}
                >
                    {t(value)}
                </button>
            ))}
        </div>
    );
}
