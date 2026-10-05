import { render, screen } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import messages from "../../messages/tr.json";
import { formats, timeZone } from "../i18n/formats";

function IntlWrapper({ children }: { children: ReactNode }) {
    return (
        <NextIntlClientProvider
            locale="tr"
            messages={messages}
            formats={formats}
            timeZone={timeZone}
        >
            {children}
        </NextIntlClientProvider>
    );
}

export function renderWithIntl(ui: ReactElement) {
    return render(ui, { wrapper: IntlWrapper });
}

/** The "Bilgi: <topic>" button of an InfoTip. */
export function infoTip(topic: string) {
    return screen.getByRole("button", {
        name: messages.review.queue.help.label.replace("{topic}", topic),
    });
}

/** The live region of the InfoTip that was just activated: the only one with text in it. */
export function openTipText() {
    const region = screen.getAllByRole("status").find((node) => node.textContent);
    if (!region) throw new Error("No InfoTip is open");
    return region;
}
