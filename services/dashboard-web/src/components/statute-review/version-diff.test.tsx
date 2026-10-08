import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { timeline } from "@/test/statute-fixtures";
import { renderWithIntl } from "@/test/intl";
import type { TimelineVersion } from "@/lib/statute-as-of";
import { MAX_CELLS } from "@/lib/word-diff";
import { VersionDiff } from "./version-diff";

const { diff } = messages.review.statutes;
const versions = timeline.filter((entry): entry is TimelineVersion => entry.kind === "version");

describe("VersionDiff", () => {
    it("marks the changed words of two versions", () => {
        const [previous, version] = versions as [TimelineVersion, TimelineVersion];
        renderWithIntl(<VersionDiff version={version} previous={previous} gapBetween={false} />);
        expect(screen.getByText(diff.legend)).toBeInTheDocument();
        expect(screen.queryByText(diff.tooLong)).not.toBeInTheDocument();
    });

    it("says so and shows both texts without marks when the article is too long to compare", () => {
        const side = (prefix: string) =>
            Array.from(
                { length: Math.ceil(Math.sqrt(MAX_CELLS)) + 1 },
                (_, i) => `${prefix}${i}`,
            ).join(" ");
        const [first, second] = versions as [TimelineVersion, TimelineVersion];
        const previous = { ...first, text: side("a") };
        const version = { ...second, text: side("b") };
        const { container } = renderWithIntl(
            <VersionDiff version={version} previous={previous} gapBetween={false} />,
        );
        expect(screen.getByText(diff.tooLong)).toBeInTheDocument();
        expect(container.querySelector("ins, del")).toBeNull();
        expect(container).toHaveTextContent(previous.text.slice(0, 40));
        expect(container).toHaveTextContent(version.text.slice(0, 40));
        expect(screen.queryByText(diff.legend)).not.toBeInTheDocument();
    });
});
