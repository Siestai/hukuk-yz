"use client";

import type { DecisionFields } from "@/lib/decision-fields";
import { FieldsCard } from "./fields-card";
import { FieldsForm } from "./fields-form";
import { useReviewSession } from "./review-session";

/** The extracted fields: read-only, or the form while the reviewer corrects them. */
export function FieldsPanel({ fields }: { fields: DecisionFields }) {
    const { mode } = useReviewSession();
    return mode === "edit" ? <FieldsForm fields={fields} /> : <FieldsCard fields={fields} />;
}
