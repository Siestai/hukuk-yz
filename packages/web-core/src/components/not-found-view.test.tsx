import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import messages from "../../messages/tr.json";
import { NotFoundView } from "./not-found-view";

vi.mock("next-intl/server", () => ({
    getTranslations: async (namespace: string) => (key: string) =>
        namespace
            .split(".")
            .reduce<Record<string, unknown>>(
                (node, part) => node[part] as Record<string, unknown>,
                messages,
            )[key],
}));

describe("NotFoundView", () => {
    it("shows Turkish text and a link home", async () => {
        render(await NotFoundView());
        expect(screen.getByText(messages.errorPage.notFound.title)).toBeInTheDocument();
        expect(screen.getByText(messages.errorPage.notFound.message)).toBeInTheDocument();
        expect(
            screen.getByRole("link", { name: messages.errorPage.notFound.home }),
        ).toHaveAttribute("href", "/");
    });
});
