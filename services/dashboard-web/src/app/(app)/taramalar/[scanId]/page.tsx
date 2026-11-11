import { notFound } from "next/navigation";

import { ScanHeader } from "@/components/journal-scans/scan-header";
import { ScanIssues } from "@/components/journal-scans/scan-issues";
import { ScanNotes } from "@/components/journal-scans/scan-notes";
import { ScanSummary } from "@/components/journal-scans/scan-summary";
import { createServerApi } from "@hukuk/web-core/api/server";
import { settle } from "@hukuk/web-core/api/settle";
import { isUuid } from "@/lib/uuid";

export default async function ScanPage({ params }: { params: Promise<{ scanId: string }> }) {
    const { scanId } = await params;
    if (!isUuid(scanId)) notFound();
    const api = await createServerApi();
    const result = await settle(
        api.GET("/journal-scans/{scan_id}", { params: { path: { scan_id: scanId } } }),
        "GET /journal-scans/{id}",
    );
    if (result.error) {
        if (result.error.code === "not_found") notFound();
        throw new Error(`GET /journal-scans/{id} answered ${result.error.code ?? "an error"}`);
    }
    const scan = result.data;

    return (
        <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
            <ScanHeader scan={scan} />
            <ScanNotes report={scan.report} />
            <ScanSummary scan={scan} />
            <ScanIssues issues={scan.report.issues} />
        </main>
    );
}
