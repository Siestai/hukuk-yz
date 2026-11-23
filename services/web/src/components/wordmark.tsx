import { cn } from "@hukuk/ui";
import { useTranslations } from "next-intl";

/**
 * "Glarus" with "by siestai" under it and the small mark: a rounded square with a serif G and a
 * turquoise dot (the full stop that ends a sentence). `dark` is for the navy sidebar and drawer.
 */
export function Wordmark({ dark = false, className }: { dark?: boolean; className?: string }) {
    const t = useTranslations("brand");
    return (
        <div className={cn("flex min-w-0 items-center gap-3", className)}>
            <svg
                viewBox="0 0 44 44"
                aria-hidden="true"
                className="size-10 shrink-0"
            >
                <rect
                    width="44"
                    height="44"
                    rx="10"
                    className={dark ? "fill-ink-inv" : "fill-navy"}
                />
                <text
                    x="21"
                    y="33"
                    textAnchor="middle"
                    fontSize="32"
                    fontWeight="600"
                    className={cn("font-serif", dark ? "fill-navy" : "fill-ink-inv")}
                >
                    {t("name").charAt(0)}
                </text>
                <circle cx="35" cy="32" r="3" className="fill-primary-bright" />
            </svg>
            <p className="flex min-w-0 flex-col leading-none">
                <span
                    className={cn(
                        "font-serif text-2xl font-semibold tracking-tight",
                        dark ? "text-ink-inv" : "text-ink",
                    )}
                >
                    {t("name")}
                </span>
                <span
                    className={cn(
                        "mt-0.5 text-xs font-medium tracking-wide",
                        dark ? "text-ink-inv-2" : "text-ink-2",
                    )}
                >
                    {t("by")}
                </span>
            </p>
        </div>
    );
}
