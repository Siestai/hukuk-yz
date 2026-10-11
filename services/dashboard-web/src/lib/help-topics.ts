/**
 * The help texts of the review screens: `review.queue.help.<topic>`. The reason texts are
 * `review.queue.help.reason.<code>`, one per code of the confidence rules.
 */
export const HELP_TOPICS = [
    "title",
    "titleApproved",
    "titleRejected",
    "titleAll",
    "subtitle",
    "subtitleOther",
    "tabPending",
    "tabApproved",
    "tabRejected",
    "tabAll",
    "bulk",
    "sort",
    "band",
    "topReasons",
    "totals",
    "filterBand",
    "filterCourt",
    "filterReason",
    "filterIssue",
    "filterSearch",
    "filterClear",
    "colConfidence",
    "colDecision",
    "colNumbers",
    "colDate",
    "colIssue",
    "colReasons",
    "colStatus",
    "cards",
    "pagination",
    "navPending",
    "navSources",
    "navKnowledgeBase",
] as const;

export type HelpName = (typeof HELP_TOPICS)[number] | `reason.${string}`;

/**
 * The help texts of the statute review screens: `review.statutes.help.<topic>`. The reason texts
 * are `review.statutes.help.reason.<code>`, one per code of the statute confidence rules. The
 * topics both queues have (tabs, band, bulk, totals, column and card tips) carry the same name in
 * both lists, so a component shared by the two screens only switches the scope.
 */
export const STATUTE_HELP_TOPICS = [
    "title",
    "titleApproved",
    "titleRejected",
    "titleAll",
    "subtitle",
    "subtitleOther",
    "lawTab4857",
    "lawTab5510",
    "tabPending",
    "tabApproved",
    "tabRejected",
    "tabAll",
    "bulk",
    "band",
    "totals",
    "filterBand",
    "filterSearch",
    "filterClear",
    "colConfidence",
    "colArticle",
    "colVersions",
    "colSnapshot",
    "colReasons",
    "colStatus",
    "cards",
    "navStatutes",
    "detailTitle",
    "confidence",
    "confidenceReasons",
    "confidenceWarnings",
    "timeline",
    "timelineKinds",
    "gap",
    "version",
    "versionHeading",
    "versionFootnotes",
    "versionEvidence",
    "versionAmendments",
    "versionCopies",
    "versionWarnings",
    "diff",
    "dateQuery",
    "actions",
    "liveNotice",
    "statusStrip",
] as const;

export type StatuteHelpName = (typeof STATUTE_HELP_TOPICS)[number] | `reason.${string}`;

export type HelpScope = "queue" | "statutes";

/** Topics that exist in both scopes, for the components the two queues share. */
export type SharedHelpName = Extract<HelpName, StatuteHelpName>;
