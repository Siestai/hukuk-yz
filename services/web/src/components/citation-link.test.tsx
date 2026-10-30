import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { CitationRef } from "@/lib/chat-types";
import { renderWithIntl } from "@/test/intl";
import { CitationLink } from "./citation-link";

const citation = {
    source_id: "statute:4857:m18",
    category: "statute",
    label: "4857 m.18/1",
    ref: "4857 m.18/1",
    review_status: "approved",
    verification: "verified",
} as CitationRef;

describe("CitationLink", () => {
    it("opens its source and shows the verified badge", async () => {
        const onOpen = vi.fn();
        renderWithIntl(<CitationLink citation={citation} onOpen={onOpen} />);
        expect(screen.getByText("teyitli")).toBeInTheDocument();
        await userEvent.click(screen.getByRole("button", { name: "Dayanağı aç: 4857 m.18/1" }));
        expect(onOpen).toHaveBeenCalledWith(citation);
    });

    it("flags a source that is not approved or not verified", () => {
        renderWithIntl(
            <CitationLink
                citation={{ ...citation, verification: "unverified", review_status: "analyzed" }}
                onOpen={vi.fn()}
            />,
        );
        expect(screen.getByText("teyitsiz")).toBeInTheDocument();
        expect(screen.getByText("onaylanmadı")).toBeInTheDocument();
    });
});
