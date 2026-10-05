"use client";

import { cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { type KeyboardEvent, type ReactNode, useId, useRef, useState } from "react";

import { PdfPanel, type PdfAvailability } from "./pdf-panel";

const TABS = ["pdf", "text"] as const;
type Tab = (typeof TABS)[number];

/** PDF and extracted text side by side as tabs; the text arrives rendered by the server. */
export function DocumentTabs({
    pdfSrc,
    pdf,
    text,
}: {
    pdfSrc: string;
    pdf: PdfAvailability;
    text: ReactNode;
}) {
    const t = useTranslations("review.detail");
    const id = useId();
    const [active, setActive] = useState<Tab>("pdf");
    const buttons = useRef<Record<Tab, HTMLButtonElement | null>>({ pdf: null, text: null });
    const label = (tab: Tab) => (tab === "pdf" ? t("tabPdf") : t("tabText"));

    function onKeyDown(event: KeyboardEvent, tab: Tab) {
        const index = TABS.indexOf(tab);
        const target = {
            ArrowRight: TABS[(index + 1) % TABS.length],
            ArrowLeft: TABS[(index + TABS.length - 1) % TABS.length],
            Home: TABS[0],
            End: TABS[TABS.length - 1],
        }[event.key];
        if (!target) return;
        event.preventDefault();
        setActive(target);
        buttons.current[target]?.focus();
    }

    return (
        <div className="grid content-start gap-3">
            <div
                role="tablist"
                aria-label={t("documentTabs")}
                className="flex gap-1 border-b border-line"
            >
                {TABS.map((tab) => (
                    <button
                        key={tab}
                        ref={(node) => {
                            buttons.current[tab] = node;
                        }}
                        id={`${id}-tab-${tab}`}
                        type="button"
                        role="tab"
                        aria-selected={active === tab}
                        aria-controls={`${id}-panel-${tab}`}
                        tabIndex={active === tab ? 0 : -1}
                        onClick={() => setActive(tab)}
                        onKeyDown={(event) => onKeyDown(event, tab)}
                        className={cn(
                            "-mb-px border-b-2 px-4 py-2 text-sm font-medium pointer-coarse:min-h-11 focus-visible:outline-2 focus-visible:outline-ring",
                            active === tab
                                ? "border-primary text-primary"
                                : "border-transparent text-ink-2",
                        )}
                    >
                        {label(tab)}
                    </button>
                ))}
            </div>
            {TABS.map((tab) => (
                <div
                    key={tab}
                    id={`${id}-panel-${tab}`}
                    role="tabpanel"
                    aria-labelledby={`${id}-tab-${tab}`}
                    tabIndex={0}
                    hidden={active !== tab}
                >
                    {tab === "pdf" ? <PdfPanel src={pdfSrc} availability={pdf} /> : text}
                </div>
            ))}
        </div>
    );
}
