import { Skeleton } from "@hukuk/ui";
import { useTranslations } from "next-intl";

const ROWS = Array.from({ length: 10 }, (_, i) => i);

export default function QueueLoading() {
    const t = useTranslations("review.queue");
    return (
        <main className="grid gap-6 p-8" aria-busy="true">
            <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
            <div className="grid gap-4 lg:grid-cols-3">
                <Skeleton className="h-36" />
                <Skeleton className="h-36" />
                <Skeleton className="h-36" />
            </div>
            <div className="grid gap-2">
                {ROWS.map((row) => (
                    <Skeleton key={row} className="h-row" />
                ))}
            </div>
        </main>
    );
}
