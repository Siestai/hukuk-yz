import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FieldRow } from "./field-row";

describe("FieldRow", () => {
    it("pairs the label with its value", () => {
        render(
            <dl>
                <FieldRow label="Mahkeme">Yargıtay</FieldRow>
            </dl>,
        );
        expect(screen.getByText("Mahkeme").tagName).toBe("DT");
        expect(screen.getByText("Yargıtay").tagName).toBe("DD");
    });

    it("stacks the label over the value on a phone and splits the row from md up", () => {
        render(
            <dl>
                <FieldRow label="Mahkeme">Yargıtay</FieldRow>
            </dl>,
        );
        const row = screen.getByText("Mahkeme").parentElement;
        expect(row).toHaveClass("grid", "md:grid-cols-3");
        expect(row).not.toHaveClass("grid-cols-3");
        expect(screen.getByText("Yargıtay")).toHaveClass("md:col-span-2");
        expect(screen.getByText("Yargıtay")).not.toHaveClass("col-span-2");
    });
});
