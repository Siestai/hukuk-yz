import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import messages from "../../../messages/tr.json";
import { renderWithIntl } from "@/test/intl";
import { ConfidenceCard } from "./confidence-card";

describe("ConfidenceCard", () => {
    it("shows score, band, reasons and warnings with labels", () => {
        renderWithIntl(
            <ConfidenceCard
                score={40}
                band="low"
                reasons={["missing_karar_no"]}
                warnings={["invalid_date", "multiple_esas_candidates:2010/1"]}
            />,
        );
        expect(screen.getByText("40")).toBeInTheDocument();
        expect(screen.getByText(messages.enums.band.low)).toBeInTheDocument();
        expect(screen.getByText(messages.enums.reason.missing_karar_no)).toBeInTheDocument();
        expect(screen.getByText(messages.enums.warning.invalid_date)).toBeInTheDocument();
        expect(screen.getByText("Birden çok esas no adayı:2010/1")).toBeInTheDocument();
    });

    it("says so when there are no reasons or warnings", () => {
        renderWithIntl(<ConfidenceCard score={100} band="high" reasons={[]} warnings={[]} />);
        expect(screen.getByText(messages.review.detail.noReasons)).toBeInTheDocument();
        expect(screen.getByText(messages.review.detail.noWarnings)).toBeInTheDocument();
    });

    it("keeps the raw code of an unknown reason or warning and flags it", () => {
        renderWithIntl(
            <ConfidenceCard
                score={40}
                band="low"
                reasons={["new_reason"]}
                warnings={["new_warning"]}
            />,
        );
        expect(screen.getByText("new_reason", { exact: false })).toHaveTextContent(
            messages.review.detail.unknownCode,
        );
        expect(screen.getByText("new_warning", { exact: false })).toHaveTextContent(
            messages.review.detail.unknownCode,
        );
    });
});
