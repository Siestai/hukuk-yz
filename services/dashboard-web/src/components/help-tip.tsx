import { InfoTip } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { HelpName, HelpScope, SharedHelpName, StatuteHelpName } from "@/lib/help-topics";

/**
 * The `InfoTip` of a help text (`review.queue.help.*`, or `review.statutes.help.*` with
 * `scope="statutes"`; the scope is typed with the names its list has). `topic` is the name of what the tip
 * explains (a label already on screen); it makes the button's accessible name "Bilgi: <topic>".
 * A name without a text (a reason code the messages do not know) renders nothing.
 */
export function HelpTip({
    name,
    scope = "queue",
    topic,
    className,
}: { topic: string; className?: string } & (
    | { name: HelpName; scope?: "queue" }
    | { name: StatuteHelpName; scope: "statutes" }
    | { name: SharedHelpName; scope?: HelpScope }
)) {
    const t = useTranslations();
    const key = `review.${scope}.help.${name}`;
    if (!t.has(key)) return null;
    return (
        <InfoTip label={t("review.queue.help.label", { topic })} className={className}>
            {t(key, { brand: t("brand.name") })}
        </InfoTip>
    );
}
