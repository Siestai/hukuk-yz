import type { components } from "@/lib/api/schema";

export type RelatedArticle = components["schemas"]["RelatedArticle"];

/** `extraction.fields` as the detail screen reads it: the API types it as a free object, so each value is checked. */
export type DecisionFields = {
    court: string;
    courtLevel: string;
    chamber: string;
    bamRegion: string;
    esasNo: string;
    kararNo: string;
    decisionDate: string;
    relatedArticles: RelatedArticle[];
    outcome: string;
    keywords: string[];
    journalIssue: number | null;
    fullText: string;
    editorialSummary: string;
};

const text = (value: unknown) => (typeof value === "string" ? value : "");
const texts = (value: unknown) =>
    Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];

function article(value: unknown): RelatedArticle | undefined {
    if (typeof value !== "object" || value === null) return undefined;
    const entry = value as Record<string, unknown>;
    return {
        statute: typeof entry.statute === "number" ? entry.statute : null,
        label: text(entry.label),
        articles: texts(entry.articles),
        raw: text(entry.raw),
    };
}

export function readFields(fields: Record<string, unknown>): DecisionFields {
    const related: unknown[] = Array.isArray(fields.related_articles)
        ? fields.related_articles
        : [];
    return {
        court: text(fields.court),
        courtLevel: text(fields.court_level),
        chamber: text(fields.chamber),
        bamRegion: text(fields.bam_region),
        esasNo: text(fields.esas_no),
        kararNo: text(fields.karar_no),
        decisionDate: text(fields.decision_date),
        relatedArticles: related.map(article).filter((a) => a !== undefined),
        outcome: text(fields.outcome),
        keywords: texts(fields.keywords),
        journalIssue: typeof fields.journal_issue === "number" ? fields.journal_issue : null,
        fullText: text(fields.full_text),
        editorialSummary: text(fields.editorial_summary),
    };
}
