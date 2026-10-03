import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import Home from "./page";

describe("Home", () => {
    it("renders only translated text", () => {
        render(
            <NextIntlClientProvider locale="tr" messages={messages}>
                <Home />
            </NextIntlClientProvider>,
        );
        expect(screen.getByText(messages.brand.name)).toBeInTheDocument();
        expect(screen.getByText(messages.foundation.ready)).toBeInTheDocument();
        expect(screen.getByRole("img", { name: messages.brand.logoLabel })).toBeInTheDocument();
    });
});
