import { InfoTip } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { HelpName } from "@/lib/help-topics";

/**
 * The `InfoTip` of a help text (`review.queue.help.*`). `topic` is the name of what the tip
 * explains (a label already on screen); it makes the button's accessible name "Bilgi: <topic>".
 * A name without a text (a reason code the messages do not know) renders nothing.
 */
export function HelpTip({
    name,
    topic,
    className,
}: {
    name: HelpName;
    topic: string;
    className?: string;
}) {
    const t = useTranslations();
    const key = `review.queue.help.${name}`;
    if (!t.has(key)) return null;
    return (
        <InfoTip label={t("review.queue.help.label", { topic })} className={className}>
            {t(key, { brand: t("brand.name") })}
        </InfoTip>
    );
}
