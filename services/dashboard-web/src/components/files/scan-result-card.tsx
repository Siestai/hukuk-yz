import { Card, CardContent, CardHeader, CardTitle } from "@hukuk/ui";
import { useFormatter, useTranslations } from "next-intl";

import { readScan, type FileOut } from "@/lib/files";
import { useCommon } from "@/lib/use-common";
import { useEnumLabels } from "@/lib/use-enum-labels";
import { ScanBadge } from "./scan-badge";

/** What the worker found: the type, pages and text length, whether OCR ran, its warnings and error. */
export function ScanResultCard({ file }: { file: FileOut }) {
    const t = useTranslations("files.detail.scan");
    const format = useFormatter();
    const labels = useEnumLabels();
    const { empty } = useCommon();
    const scan = readScan(file.scan_result);
    const count = (value: number | undefined) =>
        value === undefined ? empty : format.number(value, "integer");
    const rows = [
        { label: t("type"), value: scan.detectedType ?? file.detected_type ?? empty },
        { label: t("pages"), value: count(scan.pages) },
        { label: t("textChars"), value: count(scan.textChars) },
        { label: t("ocr"), value: scan.ocrUsed ? t("yes") : t("no") },
    ];

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
                <div role="status" className="flex items-center gap-2">
                    <ScanBadge status={file.scan_status} />
                </div>
                <dl className="grid grid-cols-1 gap-3">
                    {rows.map(({ label, value }) => (
                        <div key={label} className="grid gap-0.5">
                            <dt className="text-xs text-ink-2">{label}</dt>
                            <dd className="wrap-anywhere">{value}</dd>
                        </div>
                    ))}
                </dl>
                {scan.warnings.length > 0 ? (
                    <div className="grid gap-1">
                        <p className="text-xs text-ink-2">{t("warnings")}</p>
                        <ul className="grid gap-1">
                            {scan.warnings.map((warning) => (
                                <li key={warning} className="wrap-anywhere text-medium">
                                    {labels.scanWarning(warning)}
                                </li>
                            ))}
                        </ul>
                    </div>
                ) : null}
                {scan.error ? (
                    <div className="grid gap-1">
                        <p className="text-xs text-ink-2">{t("error")}</p>
                        <p className="font-mono text-xs wrap-anywhere text-low">{scan.error}</p>
                    </div>
                ) : null}
            </CardContent>
        </Card>
    );
}
