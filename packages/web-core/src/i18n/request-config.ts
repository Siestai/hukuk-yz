import type { AbstractIntlMessages } from "next-intl";
import { getRequestConfig } from "next-intl/server";

import { formats, timeZone } from "./formats";
import { defaultLocale } from "./locale";

/** The next-intl request config of an app: the single locale, its messages, the shared formats. */
export function requestConfig(messages: AbstractIntlMessages) {
    return getRequestConfig(async () => ({ locale: defaultLocale, messages, formats, timeZone }));
}
