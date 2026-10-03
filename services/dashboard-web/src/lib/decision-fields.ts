import type { components } from "@/lib/api/schema";

export type RelatedArticle = components["schemas"]["RelatedArticle"];

/** `extraction.fields` as the detail screen reads it: the API types it as a free object, so each value is checked. */
export type DecisionFields = {
    court: string;
    courtLevel: string;
    chamber: string;
    sourceChamber: string;
    bamRegion: string;
    decisionKind: string;
    esasNo: string;
    kararNo: string;
    decisionDate: string;
    relatedArticles: RelatedArticle[];
    jurisdiction: string;
    outcome: string;
    textCompleteness: string;
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
        sourceChamber: text(fields.source_chamber),
        bamRegion: text(fields.bam_region),
        decisionKind: text(fields.decision_kind),
        esasNo: text(fields.esas_no),
        kararNo: text(fields.karar_no),
        decisionDate: text(fields.decision_date),
        relatedArticles: related.map(article).filter((a) => a !== undefined),
        jurisdiction: text(fields.jurisdiction),
        outcome: text(fields.outcome),
        textCompleteness: text(fields.text_completeness),
        keywords: texts(fields.keywords),
        journalIssue: typeof fields.journal_issue === "number" ? fields.journal_issue : null,
        fullText: text(fields.full_text),
        editorialSummary: text(fields.editorial_summary),
    };
}

/** An HGK esas number carries the chamber it came from: "2019/1234" and chamber "9" read "2019/9-1234". */
export function esasDisplay({ esasNo, sourceChamber }: DecisionFields): string {
    const parts = /^(\d{4})\/(.+)$/.exec(esasNo);
    return sourceChamber && parts ? `${parts[1]}/${sourceChamber}-${parts[2]}` : esasNo;
}
