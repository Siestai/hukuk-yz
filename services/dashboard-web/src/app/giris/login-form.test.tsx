import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../../messages/tr.json";
import { LoginForm } from "./login-form";

const post = vi.fn();
const replace = vi.fn();
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST: post }) }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace }) }));

const answer = (status: number, body?: unknown, headers: Record<string, string> = {}) => {
    const response = new Response(null, { status, headers });
    return status < 400 ? { response, data: body } : { response, error: body };
};

async function submit(email = "a@b.c", password = "pw") {
    const user = userEvent.setup();
    render(
        <NextIntlClientProvider locale="tr" messages={messages}>
            <LoginForm next="/inceleme" />
        </NextIntlClientProvider>,
    );
    if (email) await user.type(screen.getByLabelText(messages.login.email), email);
    if (password) await user.type(screen.getByLabelText(messages.login.password), password);
    await user.click(screen.getByRole("button", { name: messages.login.submit }));
}

beforeEach(() => {
    post.mockReset();
    replace.mockReset();
});

describe("LoginForm", () => {
    it("posts the credentials as JSON and goes to next on success", async () => {
        post.mockResolvedValue(answer(200, { user: {} }));
        await submit();
        expect(post).toHaveBeenCalledWith("/auth/login", {
            body: { email: "a@b.c", password: "pw" },
        });
        await waitFor(() => expect(replace).toHaveBeenCalledWith("/inceleme"));
    });

    it.each([
        [
            "invalid credentials",
            answer(401, { error: { code: "unauthorized", params: {} } }),
            messages.errors.unauthorized,
        ],
        [
            "validation_error",
            answer(422, { error: { code: "validation_error", params: { fields: ["email"] } } }),
            messages.errors.validation_error,
        ],
        [
            "an unknown code",
            answer(500, { error: { code: "internal_error", params: {} } }),
            messages.errors.generic,
        ],
        ["a body that is not an error", answer(502), messages.errors.generic],
    ])("shows the message for %s", async (_name, result, text) => {
        post.mockResolvedValue(result);
        await submit();
        expect(await screen.findByRole("alert")).toHaveTextContent(text);
        expect(replace).not.toHaveBeenCalled();
        expect(screen.getByLabelText(messages.login.email)).toHaveFocus();
        expect(screen.getByLabelText(messages.login.password)).toHaveAttribute(
            "aria-invalid",
            "true",
        );
    });

    it.each([
        ["Retry-After 840 s", 840, {}, "14 dakika"],
        ["Retry-After 61 s rounds up", 61, {}, "2 dakika"],
        ["params when the header is missing", 0, { retry_after: 125 }, "3 dakika"],
        ["less than a minute", 5, {}, "1 dakika"],
    ])("shows the remaining minutes: %s", async (_name, header, params, minutes) => {
        post.mockResolvedValue(
            answer(
                429,
                { error: { code: "too_many_attempts", params } },
                header ? { "retry-after": String(header) } : {},
            ),
        );
        await submit();
        expect(await screen.findByRole("alert")).toHaveTextContent(
            `Çok fazla hatalı deneme. ${minutes} sonra tekrar deneyin.`,
        );
    });

    it("shows upstream_unavailable when the proxy reports it", async () => {
        post.mockResolvedValue(
            answer(502, { error: { code: "upstream_unavailable", params: {} } }),
        );
        await submit();
        expect(await screen.findByRole("alert")).toHaveTextContent(
            messages.errors.upstream_unavailable,
        );
    });

    it("shows upstream_unavailable when the request itself fails", async () => {
        post.mockRejectedValue(new TypeError("Failed to fetch"));
        await submit();
        expect(await screen.findByRole("alert")).toHaveTextContent(
            messages.errors.upstream_unavailable,
        );
    });

    it("does not send empty fields and focuses the first invalid one", async () => {
        await submit("", "pw");
        expect(post).not.toHaveBeenCalled();
        expect(screen.getByRole("alert")).toHaveTextContent(messages.login.required);
        expect(screen.getByLabelText(messages.login.email)).toHaveAttribute("aria-invalid", "true");
        expect(screen.getByLabelText(messages.login.email)).toHaveFocus();
        expect(screen.getByLabelText(messages.login.password)).toHaveAttribute(
            "aria-invalid",
            "false",
        );
    });

    it("disables the submit button while the request is pending", async () => {
        let finish: (value: unknown) => void = () => {};
        post.mockReturnValue(new Promise((resolve) => (finish = resolve)));
        await submit();
        const button = await screen.findByRole("button", { name: messages.login.submitting });
        expect(button).toBeDisabled();
        finish(answer(200, { user: {} }));
        await waitFor(() => expect(replace).toHaveBeenCalled());
    });
});
