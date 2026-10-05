import { Logo } from "@hukuk/ui";
import { useTranslations } from "next-intl";

/** Logo and name; the side navigation and the mobile bar show the same mark. */
export function Brand({ compact = false }: { compact?: boolean }) {
    const t = useTranslations("brand");
    return (
        <div className="flex items-center gap-3 text-primary">
            <Logo label={t("logoLabel")} className={compact ? "size-6" : "size-7"} />
            <div>
                <p className="text-lg font-semibold leading-none text-ink">{t("name")}</p>
                {compact ? null : (
                    <p className="mt-1 text-xs uppercase tracking-wide text-ink-3">
                        {t("subtitle")}
                    </p>
                )}
            </div>
        </div>
    );
}
