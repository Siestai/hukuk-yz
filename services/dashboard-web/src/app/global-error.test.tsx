import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import messages from "../../messages/tr.json";
import GlobalError from "./global-error";

describe("GlobalError", () => {
    it("renders its own Turkish html without providers", () => {
        const html = renderToString(<GlobalError error={new Error("x")} reset={() => {}} />);
        expect(html).toContain('lang="tr"');
        expect(html).toContain(messages.errors.generic);
        expect(html).toContain(messages.errorPage.retry);
    });
});
