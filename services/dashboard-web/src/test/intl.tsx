import { render } from "@testing-library/react";
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
