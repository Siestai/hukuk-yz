import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { describe, expect, it, vi } from "vitest";

import { UpstreamUnavailableError } from "@/lib/api/errors";
import messages from "../../messages/tr.json";
import ErrorPage from "./error";

function show(error: Error, reset = vi.fn()) {
    render(
        <NextIntlClientProvider locale="tr" messages={messages}>
            <ErrorPage error={error} reset={reset} />
        </NextIntlClientProvider>,
    );
    return reset;
}

describe("ErrorPage", () => {
    it("says the server is unreachable for an upstream error, also after serialization", () => {
        show(new UpstreamUnavailableError("down"));
        expect(screen.getByText(messages.errorPage.title)).toBeInTheDocument();
        expect(screen.getByText(messages.errors.upstream_unavailable)).toBeInTheDocument();
    });

    it("recognizes the error by name when only a plain Error arrives", () => {
        const plain = new Error("down");
        plain.name = "UpstreamUnavailableError";
        show(plain);
        expect(screen.getByText(messages.errors.upstream_unavailable)).toBeInTheDocument();
    });

    it("shows the generic message otherwise and retries through reset", async () => {
        const reset = show(new Error("boom"));
        expect(screen.getByText(messages.errors.generic)).toBeInTheDocument();
        expect(screen.queryByText("boom")).toBeNull();
        await userEvent
            .setup()
            .click(screen.getByRole("button", { name: messages.errorPage.retry }));
        expect(reset).toHaveBeenCalledOnce();
    });
});
