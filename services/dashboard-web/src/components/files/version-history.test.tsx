import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { file, FILE_ID, NEXT_FILE_ID } from "@/test/file-fixtures";
import { renderWithIntl } from "@/test/intl";
import { ScanResultCard } from "./scan-result-card";
import { VersionHistory } from "./version-history";

const newer = {
    ...file,
    id: NEXT_FILE_ID,
    original_name: "genelge-2020-39-v2.pdf",
    supersedes_id: FILE_ID,
    scan_status: "queued",
    uploaded_by_name: null,
} as const;

describe("VersionHistory", () => {
    it("lists the versions oldest first, marks the open one and links to the others", () => {
        renderWithIntl(<VersionHistory versions={[file, newer]} currentId={FILE_ID} />);
        const rows = within(
            screen.getByRole("list", { name: "Sürümler, eskiden yeniye" }),
        ).getAllByRole("listitem");
        expect(rows[0]).toHaveTextContent("Sürüm 1");
        expect(rows[0]).toHaveTextContent("Bu sayfa");
        expect(within(rows[0]!).queryByRole("link")).toBeNull();
        expect(rows[1]).toHaveTextContent("Sürüm 2");
        expect(rows[1]).toHaveTextContent("Sırada");
        expect(rows[1]).toHaveTextContent("Sistem");
        expect(
            within(rows[1]!).getByRole("link", { name: "genelge-2020-39-v2.pdf" }),
        ).toHaveAttribute("href", `/dosyalar/${NEXT_FILE_ID}`);
    });
});

describe("ScanResultCard", () => {
    it("shows type, pages, text length, OCR, and the warnings in words", () => {
        renderWithIntl(<ScanResultCard file={file} />);
        expect(screen.getByRole("status")).toHaveTextContent("Tamamlandı");
        expect(screen.getByText("pdf")).toBeInTheDocument();
        expect(screen.getByText("3")).toBeInTheDocument();
        expect(screen.getByText("4.210")).toBeInTheDocument();
        expect(screen.getByText("Hayır")).toBeInTheDocument();
        expect(screen.getByText("Bazı sayfaların metni zayıf")).toBeInTheDocument();
    });

    it("shows that OCR ran and the error of a failed scan", () => {
        renderWithIntl(
            <ScanResultCard
                file={{
                    ...file,
                    scan_status: "failed",
                    scan_result: { ocr_used: true, error: "udf_no_content" },
                }}
            />,
        );
        expect(screen.getByText("Evet")).toBeInTheDocument();
        expect(screen.getByText("udf_no_content")).toBeInTheDocument();
        expect(screen.getByText("Başarısız")).toBeInTheDocument();
    });
});
