"use client";

import { Badge, Button, Dialog } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";

import { AppNav, type AppNavProps } from "./app-nav";
import { HelpTip } from "./help-tip";
import { Brand } from "./brand";

/**
 * The top bar of screens narrower than `lg`: brand, the pending count and the button that opens
 * the navigation drawer. The drawer is the shared `Dialog`, so it traps focus, closes on Escape
 * and gives the focus back to the button.
 */
export function MobileNav(props: Omit<AppNavProps, "onNavigate">) {
    const t = useTranslations("nav");
    const format = useFormatter();
    const [open, setOpen] = useState(false);
    const button = useRef<HTMLButtonElement>(null);
    const drawerId = useId();
    const close = () => setOpen(false);

    // The bar is hidden from `lg` up: a drawer still open when the screen grows would keep the
    // page inert behind a modal nobody can see the reason for.
    useEffect(() => {
        const wide = window.matchMedia("(min-width: 1024px)");
        const closeWhenWide = (event: MediaQueryListEvent) => {
            if (event.matches) setOpen(false);
        };
        wide.addEventListener("change", closeWhenWide);
        return () => wide.removeEventListener("change", closeWhenWide);
    }, []);

    return (
        <header className="sticky top-0 z-20 flex items-center justify-between gap-3 border-b border-line bg-surface pt-safe-2 pb-2 px-safe-4 md:px-safe-6 lg:hidden">
            <Brand compact />
            <div className="flex items-center gap-3">
                {props.pending !== null ? (
                    <div className="flex items-center gap-1.5">
                        <Badge>
                            <span className="sr-only">{t("pending")}</span>
                            {format.number(props.pending, "integer")}
                        </Badge>
                        <HelpTip name="navPending" topic={t("pending")} />
                    </div>
                ) : null}
                <Button
                    ref={button}
                    variant="outline"
                    size="icon"
                    aria-label={t("menu")}
                    aria-expanded={open}
                    aria-controls={drawerId}
                    aria-haspopup="dialog"
                    onClick={() => setOpen(true)}
                >
                    <svg
                        aria-hidden="true"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth={2}
                        strokeLinecap="round"
                        className="size-5"
                    >
                        <path d="M4 6h16M4 12h16M4 18h16" />
                    </svg>
                </Button>
            </div>
            <Dialog
                id={drawerId}
                variant="drawer"
                open={open}
                onClose={close}
                title={t("menu")}
                closeLabel={t("closeMenu")}
                returnFocusTo={button}
            >
                <div className="flex flex-col gap-4">
                    <AppNav {...props} onNavigate={close} />
                </div>
            </Dialog>
        </header>
    );
}
