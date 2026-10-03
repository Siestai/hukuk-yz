import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement } from "react";

import messages from "../../messages/tr.json";
import { formats, timeZone } from "../i18n/formats";

export function renderWithIntl(ui: ReactElement) {
    return render(
        <NextIntlClientProvider
            locale="tr"
            messages={messages}
            formats={formats}
            timeZone={timeZone}
        >
            {ui}
        </NextIntlClientProvider>,
    );
}
