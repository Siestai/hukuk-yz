import { formats, timeZone } from "@hukuk/web-core/i18n/formats";
import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement, ReactNode } from "react";

import { messages } from "@/i18n/messages";

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
