import { useTranslations } from "next-intl";

import { HelpTip } from "@/components/help-tip";

/** The tip of a statute detail screen: `status` beside the outcome, `actions` above the approve and reject buttons. */
function DetailHelp({ name }: { name: "status" | "actions" }) {
    const t = useTranslations("review.statutes.detail");
    if (name === "status") {
        return <HelpTip name="statusStrip" scope="statutes" topic={t("statusTopic")} />;
    }
    return (
        <div className="flex items-center gap-2 text-sm text-ink-2">
            {t("actionsTopic")}
            <HelpTip name="actions" scope="statutes" topic={t("actionsTopic")} />
        </div>
    );
}

/** The tip beside the outcome of a statute article that left the queue (the status strip). */
export function StatusHelp() {
    return <DetailHelp name="status" />;
}

/** The line above the approve and reject buttons of a statute article, with the tip that explains them. */
export function ActionsHelp() {
    return <DetailHelp name="actions" />;
}
