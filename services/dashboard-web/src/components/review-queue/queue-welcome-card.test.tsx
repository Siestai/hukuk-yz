import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NextIntlClientProvider } from "next-intl";
import { renderToString } from "react-dom/server";
import { beforeEach, describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { WELCOME_STORAGE_KEY } from "@/lib/welcome-store";
import { renderWithIntl } from "@/test/intl";
import { WelcomeCard } from "./queue-welcome-card";
import { WelcomeToggle } from "./queue-welcome-toggle";

const { welcome } = messages.review.queue;
const title = welcome.title.replace("{brand}", messages.brand.name);

beforeEach(() => window.localStorage.clear());

describe("WelcomeCard", () => {
    it("introduces the product, the three steps and the limit of bulk approval", () => {
        renderWithIntl(<WelcomeCard />);
        const card = screen.getByRole("region", { name: title });
        expect(card).toHaveTextContent("yapay zekâ asistanı");
        expect(card).toHaveTextContent("6.300");
        expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
            welcome.stepOpen,
            welcome.stepCompare,
            welcome.stepDecide,
        ]);
        expect(card).toHaveTextContent(welcome.approved);
        expect(card).toHaveTextContent(welcome.bulk);
    });

    it("is left out of the server HTML, so a closed card never flashes and hydration matches", () => {
        const html = renderToString(
            <NextIntlClientProvider locale="tr" messages={messages}>
                <WelcomeCard />
                <WelcomeToggle />
            </NextIntlClientProvider>,
        );
        expect(html).not.toContain(title);
        expect(html).toContain(welcome.toggle);
        expect(html).toContain('aria-expanded="false"');
    });

    it("closes with the button and remembers it in the browser only", async () => {
        renderWithIntl(<WelcomeCard />);
        await userEvent.click(screen.getByRole("button", { name: welcome.dismiss }));
        expect(screen.queryByRole("region", { name: title })).toBeNull();
        expect(window.localStorage.getItem(WELCOME_STORAGE_KEY)).toBe("dismissed");
    });

    it("is not shown to a reviewer who closed it before", () => {
        window.localStorage.setItem(WELCOME_STORAGE_KEY, "dismissed");
        renderWithIntl(<WelcomeCard />);
        expect(screen.queryByRole("region", { name: title })).toBeNull();
    });

    it("comes back through the toggle and goes again through it", async () => {
        window.localStorage.setItem(WELCOME_STORAGE_KEY, "dismissed");
        renderWithIntl(
            <>
                <WelcomeToggle />
                <WelcomeCard />
            </>,
        );
        const toggle = screen.getByRole("button", { name: welcome.toggle });
        expect(toggle).toHaveAttribute("aria-expanded", "false");
        await userEvent.click(toggle);
        const card = screen.getByRole("region", { name: title });
        expect(toggle).toHaveAttribute("aria-expanded", "true");
        expect(toggle).toHaveAttribute("aria-controls", card.id);
        expect(window.localStorage.getItem(WELCOME_STORAGE_KEY)).toBeNull();
        await userEvent.click(toggle);
        expect(screen.queryByRole("region", { name: title })).toBeNull();
    });

    it("still closes when the browser refuses to store the choice", async () => {
        const original = Storage.prototype.setItem;
        Storage.prototype.setItem = () => {
            throw new Error("blocked");
        };
        try {
            renderWithIntl(<WelcomeCard />);
            await userEvent.click(screen.getByRole("button", { name: welcome.dismiss }));
            expect(screen.queryByRole("region", { name: title })).toBeNull();
        } finally {
            Storage.prototype.setItem = original;
            window.localStorage.clear();
        }
    });
});
