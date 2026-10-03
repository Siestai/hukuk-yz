import { getRequestConfig } from "next-intl/server";

import { formats, timeZone } from "./formats";
import { defaultLocale } from "./locale";

export default getRequestConfig(async () => {
    const locale = defaultLocale;
    return {
        locale,
        messages: (await import(`../../messages/${locale}.json`)).default,
        formats,
        timeZone,
    };
});
