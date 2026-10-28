import type { CitationRef } from "@/lib/chat-types";
import { CitationLink } from "./citation-link";

/** The sources under a point or a question, one link per line. */
export function CitationList({
    citations,
    onOpen,
}: {
    citations: CitationRef[];
    onOpen: (citation: CitationRef) => void;
}) {
    if (citations.length === 0) return null;
    return (
        <ul className="mt-1 grid gap-0.5">
            {citations.map((citation) => (
                <li key={`${citation.source_id}/${citation.label}`}>
                    <CitationLink citation={citation} onOpen={onOpen} />
                </li>
            ))}
        </ul>
    );
}
