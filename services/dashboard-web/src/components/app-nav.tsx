import { Badge } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

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
        { key: "sources", label: t("nav.sources") },
        { key: "knowledgeBase", label: t("nav.knowledgeBase") },
    ];
    const roleLabel = { admin: t("enums.role.admin"), reviewer: t("enums.role.reviewer") };

    return (
        <>
            <nav aria-label={t("nav.label")} className="grid flex-1 content-start gap-1 px-3">
                <NavLink href="/" onNavigate={onNavigate}>
                    {t("nav.queue")}
                    {pending !== null ? <Badge>{format.number(pending, "integer")}</Badge> : null}
                </NavLink>
                {comingLater.map(({ key, label }) => (
                    <span
                        key={key}
                        aria-disabled="true"
                        className="flex items-center justify-between rounded-md px-3 py-2 text-sm text-ink-3"
                    >
                        {label}
                        <Badge variant="outline">{t("nav.comingSoon")}</Badge>
                    </span>
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
