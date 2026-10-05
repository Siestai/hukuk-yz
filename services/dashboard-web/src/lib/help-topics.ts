/**
 * The help texts of the review screens: `review.queue.help.<topic>`. The reason texts are
 * `review.queue.help.reason.<code>`, one per code of the confidence rules.
 */
export const HELP_TOPICS = [
    "title",
    "subtitle",
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
    "colCourt",
    "colNumbers",
    "colDate",
    "colIssue",
    "colReasons",
    "cards",
    "pagination",
    "navPending",
    "navSources",
    "navKnowledgeBase",
] as const;

export type HelpName = (typeof HELP_TOPICS)[number] | `reason.${string}`;
