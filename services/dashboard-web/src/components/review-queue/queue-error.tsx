import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import { useErrorMessage } from "@/lib/use-error-message";

/** The API refused the request (4xx): shows the translated message of its error code. */
export function QueueError({
    code,
    params,
}: {
    code: string | undefined;
    params: Record<string, unknown>;
}) {
    const t = useTranslations("review.queue.error");
    const errorMessage = useErrorMessage();
    return (
        <Card role="alert">
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent>
                <p className="text-sm text-low">{errorMessage(code, params)}</p>
            </CardContent>
        </Card>
    );
}
