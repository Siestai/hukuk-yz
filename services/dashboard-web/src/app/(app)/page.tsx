import { useTranslations } from "next-intl";

export default function QueuePage() {
    const t = useTranslations("review.queue");
    return (
        <main className="p-8">
            <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
        </main>
    );
}
