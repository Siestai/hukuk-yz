import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { formats } from "../../i18n/formats";
import messages from "../../../messages/tr.json";
import { isUpstreamUnavailable } from "@/lib/api/errors";
import AppLayout from "./layout";

const get = vi.fn();
const post = vi.fn();
const replace = vi.fn();
const redirect = vi.hoisted(() =>
    vi.fn((path: string) => {
        throw new Error(`NEXT_REDIRECT ${path}`);
    }),
);
vi.mock("@/lib/api/server", () => ({ createServerApi: async () => ({ GET: get }) }));
vi.mock("@/lib/api/client", () => ({ createApiClient: () => ({ POST: post }) }));
const pathname = vi.hoisted(() => vi.fn(() => "/"));
vi.mock("next/navigation", () => ({
    redirect,
    useRouter: () => ({ replace }),
    usePathname: pathname,
}));

const user = {
    id: "1",
    email: "baran@example.test",
    display_name: "Baran Yılmaz",
    role: "reviewer",
};
const ok = (data: unknown) => ({ response: new Response(null, { status: 200 }), data });

function mockApi(summary: () => unknown) {
    get.mockImplementation(async (path: string) => (path === "/auth/me" ? ok(user) : summary()));
}

async function renderLayout() {
    render(
        <NextIntlClientProvider locale="tr" messages={messages} formats={formats}>
            {await AppLayout({ children: <p>içerik</p> })}
        </NextIntlClientProvider>,
    );
}

beforeEach(() => {
    get.mockReset();
    post.mockReset();
    replace.mockReset();
    redirect.mockClear();
    pathname.mockReturnValue("/");
});

describe("AppLayout", () => {
    it("shows the user, the role label, the pending count and the children", async () => {
        mockApi(() =>
            ok({ by_band: { high: 3, medium: 1200, low: 4 }, by_court: {}, top_reasons: [] }),
        );
        await renderLayout();
        expect(screen.getByText("Baran Yılmaz")).toBeInTheDocument();
        expect(screen.getByText(messages.enums.role.reviewer)).toBeInTheDocument();
        const queue = screen.getByRole("link", { name: new RegExp(messages.nav.queue) });
        expect(queue).toHaveAttribute("href", "/");
        expect(queue).toHaveTextContent("1.207");
        expect(screen.getByText("içerik")).toBeInTheDocument();
    });

    it("marks the future sections as coming later", async () => {
        mockApi(() => ok({ by_band: {}, by_court: {}, top_reasons: [] }));
        await renderLayout();
        for (const label of [messages.nav.sources, messages.nav.knowledgeBase]) {
            const item = screen.getByText(label).closest("[aria-disabled]");
            expect(item).toHaveAttribute("aria-disabled", "true");
            expect(item).toHaveTextContent(messages.nav.comingSoon);
        }
    });

    it.each([
        ["an error status", () => ({ response: new Response(null, { status: 500 }) })],
        [
            "a network failure",
            () => {
                throw new TypeError("fetch failed");
            },
        ],
    ])("shows no badge when the summary fails with %s", async (_name, summary) => {
        mockApi(summary);
        await renderLayout();
        const queue = screen.getByRole("link", { name: new RegExp(messages.nav.queue) });
        expect(queue.querySelector('[data-slot="badge"]')).toBeNull();
        expect(screen.getByText("içerik")).toBeInTheDocument();
    });

    it("drops a stale session when the API answers 401", async () => {
        get.mockResolvedValue({ response: new Response(null, { status: 401 }) });
        await expect(AppLayout({ children: null })).rejects.toThrow("NEXT_REDIRECT /oturum-sonu");
    });

    it("raises upstream_unavailable when /auth/me cannot be fetched", async () => {
        get.mockRejectedValue(new TypeError("fetch failed"));
        const error = await AppLayout({ children: null }).catch((e: Error) => e);
        expect(error).toBeInstanceOf(Error);
        expect(isUpstreamUnavailable(error as Error)).toBe(true);
    });

    it("raises upstream_unavailable when /auth/me answers 500", async () => {
        get.mockResolvedValue({ response: new Response(null, { status: 500 }) });
        const error = await AppLayout({ children: null }).catch((e: Error) => e);
        expect(isUpstreamUnavailable(error as Error)).toBe(true);
        expect(redirect).not.toHaveBeenCalled();
    });

    it("raises a generic error for other failures", async () => {
        get.mockResolvedValue({ response: new Response(null, { status: 403 }) });
        const error = await AppLayout({ children: null }).catch((e: Error) => e);
        expect(isUpstreamUnavailable(error as Error)).toBe(false);
    });

    it("marks the queue link as current only on its own path", async () => {
        mockApi(() => ok({ by_band: {}, by_court: {}, top_reasons: [] }));
        await renderLayout();
        const queue = screen.getByRole("link", { name: new RegExp(messages.nav.queue) });
        expect(queue).toHaveAttribute("aria-current", "page");
        cleanup();
        pathname.mockReturnValue("/baska");
        await renderLayout();
        expect(
            screen.getByRole("link", { name: new RegExp(messages.nav.queue) }),
        ).not.toHaveAttribute("aria-current");
    });

    it("logs out through the API and goes to /giris", async () => {
        mockApi(() => ok({ by_band: {}, by_court: {}, top_reasons: [] }));
        post.mockResolvedValue({ response: new Response(null, { status: 204 }) });
        await renderLayout();
        await userEvent.setup().click(screen.getByRole("button", { name: messages.nav.logout }));
        expect(post).toHaveBeenCalledWith("/auth/logout");
        expect(replace).toHaveBeenCalledWith("/giris");
    });
});
