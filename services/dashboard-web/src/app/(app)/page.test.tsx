import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import QueuePage from "./page";

describe("QueuePage", () => {
    it("renders the page header", () => {
        render(
            <NextIntlClientProvider locale="tr" messages={messages}>
                <QueuePage />
            </NextIntlClientProvider>,
        );
        expect(
            screen.getByRole("heading", { level: 1, name: messages.review.queue.title }),
        ).toBeInTheDocument();
    });
});
