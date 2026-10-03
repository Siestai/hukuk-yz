import type { components } from "@/lib/api/schema";
import type { DecisionFields, RelatedArticle } from "@/lib/decision-fields";
import { COURTS } from "@/lib/queue-params";

export type DecisionEdits = components["schemas"]["DecisionEdits"];
type Choices<K extends keyof DecisionEdits> = readonly NonNullable<DecisionEdits[K]>[];

export const EDIT_COURTS: Choices<"court"> = COURTS;
export const COURT_LEVELS: Choices<"court_level"> = [
    "aym",
    "ibk",
    "hgk_iddk",
    "daire",
    "bam_bim",
    "ilk_derece",
    "international",
];
export const JURISDICTIONS: Choices<"jurisdiction"> = ["adli", "idari"];
export const OUTCOMES: Choices<"outcome"> = [
    "bozma",
    "onama",
    "duzelterek_onama",
    "kabul",
    "red",
    "ihlal",
    "ihlal_yok",
];
export const TEXT_COMPLETENESS: Choices<"text_completeness"> = ["full", "excerpt", "summary_only"];

/** The fields edited as one line of text or one choice; the values of the form are strings. */
export const SCALAR_FIELDS = [
    "court",
    "court_level",
    "chamber",
    "source_chamber",
    "bam_region",
    "decision_kind",
    "esas_no",
    "karar_no",
    "decision_date",
    "jurisdiction",
    "outcome",
    "text_completeness",
] as const satisfies readonly (keyof DecisionEdits)[];
export type ScalarField = (typeof SCALAR_FIELDS)[number];
export type EditField = keyof DecisionEdits;

const FIELD_OF: Record<ScalarField, keyof DecisionFields> = {
    court: "court",
    court_level: "courtLevel",
    chamber: "chamber",
    source_chamber: "sourceChamber",
    bam_region: "bamRegion",
    decision_kind: "decisionKind",
    esas_no: "esasNo",
    karar_no: "kararNo",
    decision_date: "decisionDate",
    jurisdiction: "jurisdiction",
    outcome: "outcome",
    text_completeness: "textCompleteness",
};

/** A reviewer may not leave these empty; the API takes edits that are never null, so no field can be cleared. */
const REQUIRED: readonly ScalarField[] = ["esas_no", "karar_no"];

export type ArticleRow = {
    key: number;
    statute: string;
    /** Article numbers, comma separated. */
    articles: string;
    /** The entry this row was read from; null for a row added by hand. */
    source: RelatedArticle | null;
};

export type FormValues = Record<ScalarField, string> & {
    /** One keyword per line. */
    keywords: string;
    related_articles: ArticleRow[];
};

export const FIELD_ERRORS = ["blank", "invalid_date", "invalid_statute"] as const;
export type FieldError = (typeof FIELD_ERRORS)[number];

export type BuiltEdits = {
    /** Only what changed. */
    edits: DecisionEdits;
    errors: Partial<Record<EditField, FieldError>>;
    /** Fields the reviewer emptied: nothing is sent for them, the form says so. */
    ignored: EditField[];
};

export const EDIT_FIELDS = [...SCALAR_FIELDS, "keywords", "related_articles"] as const;

export function scalarValue(fields: DecisionFields, name: ScalarField): string {
    return fields[FIELD_OF[name]] as string;
}

const statuteText = (entry: RelatedArticle) =>
    entry.statute === null ? "" : String(entry.statute);

export function initialValues(fields: DecisionFields): FormValues {
    const values = Object.fromEntries(
        SCALAR_FIELDS.map((name) => [name, scalarValue(fields, name)]),
    ) as Record<ScalarField, string>;
    return {
        ...values,
        keywords: fields.keywords.join("\n"),
        related_articles: fields.relatedArticles.map((source, key) => ({
            key,
            statute: statuteText(source),
            articles: source.articles.join(", "),
            source,
        })),
    };
}

export function isRealIsoDate(value: string): boolean {
    const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
    if (!parts) return false;
    const [year, month, day] = [Number(parts[1]), Number(parts[2]), Number(parts[3])];
    const date = new Date(Date.UTC(year, month - 1, day));
    return (
        date.getUTCFullYear() === year &&
        date.getUTCMonth() === month - 1 &&
        date.getUTCDate() === day
    );
}

const list = (text: string, separator: RegExp) =>
    text
        .split(separator)
        .map((part) => part.trim())
        .filter(Boolean);

const same = (a: readonly unknown[], b: readonly unknown[]) =>
    JSON.stringify(a) === JSON.stringify(b);
const canonical = (entry: RelatedArticle) =>
    [entry.statute, entry.label, entry.articles, entry.raw] as const;

/**
 * Turns the form into the `edits` of the API. Untouched entries of `related_articles` go back as
 * read (their `raw` line is the parser's evidence); entries added by hand have `raw` "".
 */
export function buildEdits(fields: DecisionFields, values: FormValues): BuiltEdits {
    const edits: Record<string, unknown> = {};
    const errors: BuiltEdits["errors"] = {};
    const ignored: EditField[] = [];

    for (const name of SCALAR_FIELDS) {
        const value = values[name].trim();
        if (value === scalarValue(fields, name)) continue;
        if (value === "") {
            if (REQUIRED.includes(name)) errors[name] = "blank";
            else ignored.push(name);
        } else if (name === "decision_date" && !isRealIsoDate(value)) {
            errors[name] = "invalid_date";
        } else {
            edits[name] = value;
        }
    }

    const keywords = list(values.keywords, /\r?\n/);
    if (!same(keywords, fields.keywords)) {
        if (keywords.length === 0) ignored.push("keywords");
        else edits.keywords = keywords;
    }

    const entries: RelatedArticle[] = [];
    for (const row of values.related_articles) {
        const statute = row.statute.trim();
        const articles = list(row.articles, /,/);
        const { source } = row;
        if (source && statute === statuteText(source) && same(articles, source.articles)) {
            entries.push(source);
        } else if (statute === "" && articles.length === 0) {
            continue; // a blank row is a removed row
        } else if (!/^(\d{1,6})?$/.test(statute)) {
            errors.related_articles = "invalid_statute";
        } else {
            const unchangedStatute = source !== null && statute === statuteText(source);
            entries.push({
                statute: statute === "" ? null : Number(statute),
                label: unchangedStatute ? source.label : "",
                articles,
                raw: source?.raw ?? "",
            });
        }
    }
    if (!same(entries.map(canonical), fields.relatedArticles.map(canonical))) {
        if (entries.length === 0) ignored.push("related_articles");
        else edits.related_articles = entries;
    }

    return { edits: edits as DecisionEdits, errors, ignored };
}
