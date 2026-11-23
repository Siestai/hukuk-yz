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
            role="group"
            aria-label={t("label")}
            className={cn("grid grid-cols-3 gap-1 rounded-card bg-sunken p-1", className)}
        >
            {MODES.map((value) => (
                <button
                    key={value}
                    type="button"
                    aria-pressed={mode === value}
                    onClick={() => onChange(value)}
                    className={cn(
                        "min-h-11 rounded-md border px-1 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-ring",
                        mode === value
                            ? "lip lip-line border-input bg-surface text-ink"
                            : "border-transparent text-ink-2",
                    )}
                >
                    {t(value)}
                </button>
            ))}
        </div>
    );
}
