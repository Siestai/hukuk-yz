import {
    COURT_LEVELS,
    EDIT_COURTS,
    JURISDICTIONS,
    OUTCOMES,
    TEXT_COMPLETENESS,
    type ScalarField,
} from "@/lib/decision-edits";
import type { useEnumLabels } from "@/lib/use-enum-labels";

type Labeller = (value: string) => string;

/** Fields shown as a choice; the stored value stays an option even when it is not one of the known ones. */
export const CHOICES: Partial<
    Record<
        ScalarField,
        {
            options: readonly string[];
            label: (labels: ReturnType<typeof useEnumLabels>) => Labeller;
        }
    >
> = {
    court: { options: EDIT_COURTS, label: (l) => l.court },
    court_level: { options: COURT_LEVELS, label: (l) => l.courtLevel },
    jurisdiction: { options: JURISDICTIONS, label: (l) => l.jurisdiction },
    outcome: { options: OUTCOMES, label: (l) => l.outcome },
    text_completeness: { options: TEXT_COMPLETENESS, label: (l) => l.textCompleteness },
};
