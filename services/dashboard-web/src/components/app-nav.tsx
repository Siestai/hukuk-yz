import { Badge } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

import { HelpTip } from "./help-tip";
import { LogoutButton } from "./logout-button";
import { NavLink } from "./nav-link";

export type AppNavProps = {
    user: { display_name: string; role: "admin" | "reviewer" };
    /** Pending decisions; null when the count could not be fetched. */
    pending: number | null;
    /** Called when a link is followed (the drawer closes). */
    onNavigate?: () => void;
};

/** The navigation links and the signed-in user: the content of the side navigation and of the drawer. */
export function AppNav({ user, pending, onNavigate }: AppNavProps) {
    const t = useTranslations();
    const format = useFormatter();
    const comingLater = [
        { key: "sources", help: "navSources", label: t("nav.sources") },
        { key: "knowledgeBase", help: "navKnowledgeBase", label: t("nav.knowledgeBase") },
    ] as const;
    const roleLabel = { admin: t("enums.role.admin"), reviewer: t("enums.role.reviewer") };

    return (
        <>
            <nav aria-label={t("nav.label")} className="grid flex-1 content-start gap-1 px-3">
                <div className="flex items-center gap-2">
                    <div className="min-w-0 flex-1">
                        <NavLink href="/" onNavigate={onNavigate}>
                            {t("nav.queue")}
                            {pending !== null ? (
                                <Badge>{format.number(pending, "integer")}</Badge>
                            ) : null}
                        </NavLink>
                    </div>
                    {pending !== null ? (
                        <HelpTip name="navPending" topic={t("nav.pending")} />
                    ) : null}
                </div>
                <NavLink href="/mevzuat" onNavigate={onNavigate}>
                    {t("nav.statutes")}
                </NavLink>
                {comingLater.map(({ key, help, label }) => (
                    <div key={key} className="flex items-center gap-2">
                        <span
                            aria-disabled="true"
                            className="flex min-w-0 flex-1 items-center justify-between rounded-md px-3 py-2 text-sm text-ink-3"
                        >
                            {label}
                            <Badge variant="outline">{t("nav.comingSoon")}</Badge>
                        </span>
                        <HelpTip name={help} topic={label} />
                    </div>
                ))}
            </nav>
            <div className="grid gap-3 border-t border-line p-4">
                <div>
                    <p className="text-sm font-medium text-ink">{user.display_name}</p>
                    <p className="text-xs text-ink-2">{roleLabel[user.role]}</p>
                </div>
                <LogoutButton />
            </div>
        </>
    );
}
