"use client";

import { useTranslations } from "next-intl";

import { setWelcomeDismissed, useWelcomeDismissed } from "@/lib/welcome-store";
import { WELCOME_CARD_ID } from "./welcome-card-id";

/** "Bu ekran nedir?": brings the welcome card back after it was closed. */
export function WelcomeToggle() {
    const t = useTranslations();
    const dismissed = useWelcomeDismissed();
    return (
        <button
            type="button"
            aria-expanded={!dismissed}
            aria-controls={dismissed ? undefined : WELCOME_CARD_ID}
            onClick={() => setWelcomeDismissed(!dismissed)}
            className="inline-flex items-center rounded-md text-sm font-medium text-primary underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring pointer-coarse:min-h-11"
        >
            {t("review.queue.welcome.toggle")}
        </button>
    );
}
