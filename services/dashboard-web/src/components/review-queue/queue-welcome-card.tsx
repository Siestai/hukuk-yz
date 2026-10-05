"use client";

import { Button, Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId } from "react";

import { setWelcomeDismissed, useWelcomeDismissed } from "@/lib/welcome-store";
import { WELCOME_CARD_ID } from "./welcome-card-id";

/** The introduction at the top of the queue; "Anladım" closes it and the browser remembers. */
export function WelcomeCard() {
    const t = useTranslations();
    const dismissed = useWelcomeDismissed();
    const titleId = useId();
    if (dismissed) return null;

    return (
        <Card
            id={WELCOME_CARD_ID}
            role="region"
            aria-labelledby={titleId}
            className="bg-primary-soft"
        >
            <CardHeader>
                <CardTitle>
                    <h2 id={titleId}>
                        {t("review.queue.welcome.title", { brand: t("brand.name") })}
                    </h2>
                </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm text-ink">
                <p>{t("review.queue.welcome.intro", { brand: t("brand.name") })}</p>
                <p>{t("review.queue.welcome.what")}</p>
                <div className="grid gap-1">
                    <p className="font-medium">{t("review.queue.welcome.stepsTitle")}</p>
                    <ol className="list-decimal pl-5">
                        <li>{t("review.queue.welcome.stepOpen")}</li>
                        <li>{t("review.queue.welcome.stepCompare")}</li>
                        <li>{t("review.queue.welcome.stepDecide")}</li>
                    </ol>
                </div>
                <p>{t("review.queue.welcome.approved")}</p>
                <p>{t("review.queue.welcome.bulk")}</p>
                <div className="grid md:flex md:justify-end">
                    <Button type="button" onClick={() => setWelcomeDismissed(true)}>
                        {t("review.queue.welcome.dismiss")}
                    </Button>
                </div>
            </CardContent>
        </Card>
    );
}
