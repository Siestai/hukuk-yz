import { Badge, Logo } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

import { LogoutButton } from "./logout-button";
import { NavLink } from "./nav-link";

type SideNavProps = {
    user: { display_name: string; role: "admin" | "reviewer" };
    /** Pending decisions; null when the count could not be fetched. */
    pending: number | null;
};

export function SideNav({ user, pending }: SideNavProps) {
    const t = useTranslations();
    const format = useFormatter();
    const comingLater = [
        { key: "sources", label: t("nav.sources") },
        { key: "knowledgeBase", label: t("nav.knowledgeBase") },
    ];
    const roleLabel = { admin: t("enums.role.admin"), reviewer: t("enums.role.reviewer") };

    return (
        <aside className="flex w-64 shrink-0 flex-col border-r border-line bg-surface">
            <div className="flex items-center gap-3 p-5 text-primary">
                <Logo label={t("brand.logoLabel")} className="size-7" />
                <div>
                    <p className="text-lg font-semibold leading-none text-ink">{t("brand.name")}</p>
                    <p className="mt-1 text-xs uppercase tracking-wide text-ink-3">
                        {t("brand.subtitle")}
                    </p>
                </div>
            </div>
            <nav aria-label={t("nav.label")} className="grid flex-1 content-start gap-1 px-3">
                <NavLink href="/">
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
        </aside>
    );
}
