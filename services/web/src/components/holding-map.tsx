"use client";

import { Card, cn, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@hukuk/ui";
import { useTranslations } from "next-intl";

import type { CitationRef, HoldingRow } from "@/lib/chat-types";
import { CitationLink } from "./citation-link";

type Result = HoldingRow["result"];

const TONE: Record<Result, string> = {
    met: "text-high",
    not_met: "text-low",
    not_applicable: "text-ink-3",
    unknown: "text-medium",
};

function useRows(rows: HoldingRow[]) {
    const t = useTranslations("chat.holding");
    return rows.map((row) => ({
        key: `${row.citation.source_id}/${row.condition}`,
        condition: row.condition,
        citation: row.citation,
        value: row.fact_value ?? t("unknownValue"),
        symbol: t(`symbols.${row.result}`),
        label: t(`results.${row.result}`),
        tone: TONE[row.result],
    }));
}

/**
 * "Koşullar olaya uyuyor mu?": each condition of the norm with its source, the case's value and the
 * outcome. A table where the answer column is wide enough, one card per row below that (the
 * container, not the screen, decides: the source panel narrows it).
 */
export function HoldingMap({
    rows,
    onOpenCitation,
}: {
    rows: HoldingRow[];
    onOpenCitation: (citation: CitationRef) => void;
}) {
    const t = useTranslations("chat.holding");
    const items = useRows(rows);
    return (
        <Card className="overflow-hidden">
            <h3 className="p-4 pb-3 font-semibold text-ink">{t("title")}</h3>
            <div className="hidden @xl:block">
                <Table className="table-fixed">
                    <TableHeader>
                        <TableRow className="h-9">
                            <TableHead className="w-1/2">{t("condition")}</TableHead>
                            <TableHead>{t("inCase")}</TableHead>
                            <TableHead className="w-24">{t("result")}</TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {items.map((item) => (
                            <TableRow key={item.key} className="align-top">
                                <TableCell className="py-3 align-top whitespace-normal">
                                    <p className="wrap-anywhere text-ink">{item.condition}</p>
                                    <CitationLink
                                        citation={item.citation}
                                        onOpen={onOpenCitation}
                                    />
                                </TableCell>
                                <TableCell className="py-3 align-top wrap-anywhere text-ink">
                                    {item.value}
                                </TableCell>
                                <TableCell
                                    className={cn("py-3 align-top font-semibold", item.tone)}
                                >
                                    <span aria-hidden="true">{item.symbol}</span>{" "}
                                    <span className="text-xs">{item.label}</span>
                                </TableCell>
                            </TableRow>
                        ))}
                    </TableBody>
                </Table>
            </div>
            <ul className="grid grid-cols-1 divide-y divide-line-2 border-t border-line-2 @xl:hidden">
                {items.map((item) => (
                    <li key={item.key} className="grid gap-1 p-4">
                        <p className="wrap-anywhere text-ink">{item.condition}</p>
                        <CitationLink citation={item.citation} onOpen={onOpenCitation} />
                        <p className="flex items-baseline justify-between gap-3 text-sm">
                            <span className="wrap-anywhere text-ink-2">{item.value}</span>
                            <span className={cn("shrink-0 font-semibold", item.tone)}>
                                <span aria-hidden="true">{item.symbol}</span>{" "}
                                <span className="text-xs">{item.label}</span>
                            </span>
                        </p>
                    </li>
                ))}
            </ul>
        </Card>
    );
}
