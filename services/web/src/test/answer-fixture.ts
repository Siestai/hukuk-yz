import type { Answer, SourceGap } from "@/lib/chat-types";
import sb001 from "../../../../eval/fixtures/SB-001.answer.json";

/** The conditional SB-001 answer of the fixture backend. */
export const conditionalAnswer = sb001 as Answer;

/** The "kaynak yetersiz" content of a fallback: one source missing, one fact given. */
export const sourceGap: SourceGap = {
    topic: "İşe iade",
    missing_sources: [
        { ref: "4857 m.18", reason: "not_found" },
        { ref: "7036 m.3", reason: "not_in_force" },
    ],
    given_facts: [{ key: "kidem", label: "Kıdem", value: "5 ay", status: "known" }],
    next_step: "Bu soru, şu kaynaklar bilgi tabanına eklendiğinde cevaplanabilir: 4857 m.18.",
};
