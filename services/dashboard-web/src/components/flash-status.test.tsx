import { screen, waitFor } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import messages from "../../messages/tr.json";
import { formats, timeZone } from "@/i18n/formats";
import { renderWithIntl } from "@/test/intl";
import { FlashStatus } from "./flash-status";

const refresh = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));

function open(search: string) {
    window.history.replaceState(null, "", `/kararlar/x${search}`);
}

beforeEach(() => {
    vi.clearAllMocks();
    open("");
});

describe("FlashStatus", () => {
    it("is an empty status region on the first paint", () => {
        const html = renderToStaticMarkup(
            <NextIntlClientProvider
                locale="tr"
                messages={messages}
                formats={formats}
                timeZone={timeZone}
            >
                <FlashStatus notice={{ flash: "approved" }} atQueue={false} />
            </NextIntlClientProvider>,
        );
        expect(html).toBe('<div role="status"></div>');
    });

    it("receives its text in an effect", async () => {
        open("?flash=approved");
        renderWithIntl(<FlashStatus notice={{ flash: "approved" }} atQueue={false} />);
        await waitFor(() =>
            expect(screen.getByRole("status")).toHaveTextContent("Karar onaylandı."),
        );
    });

    it("adds the finished notice only at the queue", async () => {
        open("?flash=rejected&done=1");
        const { unmount } = renderWithIntl(
            <FlashStatus notice={{ flash: "rejected", done: true }} atQueue={false} />,
        );
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("reddedildi."));
        expect(screen.getByRole("status")).not.toHaveTextContent("Kuyruk bitti");
        unmount();
        open("?flash=rejected&done=1");
        renderWithIntl(<FlashStatus notice={{ flash: "rejected", done: true }} atQueue />);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Kuyruk bitti"));
    });

    it("refreshes the server-rendered counts once, and keeps the text when the URL loses the notice", async () => {
        open("?band=low&pos=4&flash=approved&done=1");
        const { rerender } = renderWithIntl(
            <FlashStatus notice={{ flash: "approved", done: true }} atQueue />,
        );
        await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
        expect(window.location.search).toBe("?band=low&pos=4");
        rerender(<FlashStatus notice={{ flash: undefined, done: false }} atQueue />);
        expect(screen.getByRole("status")).toHaveTextContent("Karar onaylandı.");
        expect(refresh).toHaveBeenCalledTimes(1);
    });

    it("does nothing without a notice", () => {
        open("?band=low");
        renderWithIntl(<FlashStatus notice={{}} atQueue />);
        expect(refresh).not.toHaveBeenCalled();
        expect(screen.getByRole("status")).toBeEmptyDOMElement();
        expect(window.location.search).toBe("?band=low");
    });
});
