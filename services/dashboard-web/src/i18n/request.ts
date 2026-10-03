import { getRequestConfig } from "next-intl/server";

import { formats, timeZone } from "./formats";
import { routing } from "./routing";

export default getRequestConfig(async () => {
    const locale = routing.defaultLocale;
    return {
        locale,
        messages: (await import(`../../messages/${locale}.json`)).default,
        formats,
        timeZone,
    };
});
