import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { messages } from "@/i18n/messages";
import { renderWithIntl } from "@/test/intl";
import { FileTabs } from "./file-tabs";

const { tabs } = messages.files.list;
const link = (name: RegExp) =>
    within(screen.getByRole("navigation", { name: tabs.label })).getByRole("link", { name });

describe("FileTabs", () => {
    it("shows Tümü and Onay bekliyor with the number waiting, the open one marked", () => {
        renderWithIntl(<FileTabs params={{}} pending={12} />);
        expect(link(/Tümü/)).toHaveAttribute("aria-current", "page");
        expect(link(/Onay bekliyor/)).toHaveTextContent("12");
        expect(link(/Onay bekliyor/)).not.toHaveAttribute("aria-current");
        expect(link(/Onay bekliyor/)).toHaveAttribute("href", "/dosyalar?onay=bekliyor");
    });

    it("keeps the filters, drops the page and marks the pending tab when it is open", () => {
        renderWithIntl(
            <FileTabs
                params={{ docType: "genelge", review: "pending", cursor: "abc" }}
                pending={100}
            />,
        );
        expect(link(/Onay bekliyor/)).toHaveAttribute("aria-current", "page");
        expect(link(/Onay bekliyor/)).toHaveTextContent("100");
        expect(link(/Tümü/)).toHaveAttribute("href", "/dosyalar?tur=genelge");
    });

    it("shows no number when the count is unknown", () => {
        renderWithIntl(<FileTabs params={{}} pending={null} />);
        expect(link(/Onay bekliyor/)).toHaveTextContent(/^Onay bekliyor$/);
    });
});
