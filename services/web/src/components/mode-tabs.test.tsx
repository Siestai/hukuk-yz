import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/intl";
import { ModeTabs } from "./mode-tabs";

describe("ModeTabs", () => {
    it("marks the current mode and reports the one picked", async () => {
        const onChange = vi.fn();
        renderWithIntl(<ModeTabs mode="short" onChange={onChange} />);
        expect(screen.getByRole("tab", { name: "Kısa" })).toHaveAttribute("aria-selected", "true");
        await userEvent.click(screen.getByRole("tab", { name: "Gerekçeli" }));
        expect(onChange).toHaveBeenCalledWith("reasoned");
    });
});
