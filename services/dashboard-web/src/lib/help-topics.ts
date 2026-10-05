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
