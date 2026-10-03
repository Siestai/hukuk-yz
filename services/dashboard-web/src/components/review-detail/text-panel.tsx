import { useTranslations } from "next-intl";

type Props = { fullText: string; editorialSummary: string };

/** Paragraphs are the blank-line separated blocks of the stored text; line breaks inside one stay. */
const paragraphs = (text: string) => text.split(/\n\s*\n/).filter((p) => p.trim() !== "");

export function TextPanel({ fullText, editorialSummary }: Props) {
    const t = useTranslations("review.detail.text");
    return (
        <div className="grid gap-4">
            {editorialSummary ? (
                <aside
                    aria-label={t("editorialLabel")}
                    className="grid gap-2 rounded-md border border-dashed border-border bg-surface-2 p-4"
                >
                    <p className="text-xs font-medium text-ink-3">{t("editorialLabel")}</p>
                    <p className="text-xs text-ink-3">{t("editorialNote")}</p>
                    <p className="whitespace-pre-line font-serif text-sm text-ink-2">
                        {editorialSummary}
                    </p>
                </aside>
            ) : null}
            {fullText ? (
                <article
                    aria-label={t("title")}
                    className="grid gap-4 font-serif text-base text-ink"
                >
                    {paragraphs(fullText).map((paragraph, i) => (
                        <p key={i} className="whitespace-pre-line">
                            {paragraph}
                        </p>
                    ))}
                </article>
            ) : (
                <p className="text-sm text-ink-2">{t("none")}</p>
            )}
        </div>
    );
}
