import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { TextPanel } from "./text-panel";

describe("TextPanel", () => {
    it("keeps the paragraphs of the text in a serif block", () => {
        renderWithIntl(
            <TextPanel fullText={"Birinci.\n\nİkinci\nsatır.\n\n\n"} editorialSummary="" />,
        );
        const article = screen.getByRole("article");
        expect(article).toHaveClass("font-serif");
        expect(article.querySelectorAll("p")).toHaveLength(2);
        expect(article).toHaveTextContent("Birinci.İkinci satır.");
        expect(screen.queryByText(messages.review.detail.text.editorialLabel)).toBeNull();
    });

    it("puts the journal summary in its own box labelled as editorial content", () => {
        renderWithIntl(<TextPanel fullText="Metin." editorialSummary="Dergi özeti metni" />);
        const box = screen.getByRole("complementary", { name: "Dergi özeti · editoryal içerik" });
        expect(box).toHaveTextContent("Dergi özeti metni");
        expect(screen.getByRole("article")).not.toHaveTextContent("Dergi özeti metni");
    });

    it("says so when the record has no text", () => {
        renderWithIntl(<TextPanel fullText="" editorialSummary="Özet" />);
        expect(screen.getByText(messages.review.detail.text.none)).toBeInTheDocument();
        expect(screen.queryByRole("article")).toBeNull();
    });
});
