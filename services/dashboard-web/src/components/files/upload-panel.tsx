"use client";

import { Button, Card, CardContent, CardHeader, CardTitle, cn } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRef, useState, type DragEvent } from "react";

import { ACCEPT, fileHref } from "@/lib/files";
import { uploadFile } from "@/lib/upload-file";
import { UploadItem, type UploadEntry, type UploadStatus } from "./upload-item";

/** A new file (`POST /files`) or the next version of `fileId` (`POST /files/{id}/versions`). */
export type UploadTarget = { kind: "new" } | { kind: "version"; fileId: string };

let counter = 0;

/**
 * Drop zone and file picker, and the upload of the chosen files one after another with progress,
 * scan and result for each. Nothing has to be typed: the optional fields of a file are folded
 * away and whatever is typed there counts as the user's own value. A new version takes one file
 * and leaves out what the API copies from the previous version.
 */
export function UploadPanel({ target, isAdmin }: { target: UploadTarget; isAdmin: boolean }) {
    const t = useTranslations("files.upload");
    const router = useRouter();
    const input = useRef<HTMLInputElement>(null);
    const [entries, setEntries] = useState<UploadEntry[]>([]);
    const [dragging, setDragging] = useState(false);
    const [busy, setBusy] = useState(false);
    const isVersion = target.kind === "version";
    const url = isVersion ? `/api/files/${target.fileId}/versions` : "/api/files";

    function add(files: FileList | null) {
        if (!files || files.length === 0) return;
        const added = Array.from(files).map((file): UploadEntry => ({
            key: `file-${counter++}`,
            file,
            fields: {},
            status: { kind: "ready" },
        }));
        setEntries((current) => (isVersion ? added.slice(0, 1) : [...current, ...added]));
    }

    function patch(key: string, change: Partial<UploadEntry>) {
        setEntries((current) =>
            current.map((entry) => (entry.key === key ? { ...entry, ...change } : entry)),
        );
    }

    function onDrop(event: DragEvent) {
        event.preventDefault();
        setDragging(false);
        add(event.dataTransfer.files);
    }

    async function submit() {
        const waiting = entries.filter(
            (entry) => entry.status.kind === "ready" || entry.status.kind === "failed",
        );
        setBusy(true);
        let created: string | undefined;
        for (const entry of waiting) {
            const status = (next: UploadStatus) => patch(entry.key, { status: next });
            status({ kind: "uploading", fraction: 0 });
            const outcome = await uploadFile(url, entry.file, entry.fields, (fraction) =>
                status({ kind: "uploading", fraction }),
            );
            if (outcome.ok) {
                created = outcome.file.id;
                status({ kind: "done", id: outcome.file.id });
            } else {
                status({ kind: "failed", code: outcome.code, params: outcome.params });
            }
        }
        setBusy(false);
        if (created === undefined) return;
        if (isVersion) router.push(fileHref(created));
        else router.refresh();
    }

    const waiting = entries.some((e) => e.status.kind === "ready" || e.status.kind === "failed");

    return (
        <Card>
            <CardHeader>
                <CardTitle>{isVersion ? t("titleVersion") : t("title")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
                <div
                    role="group"
                    aria-label={t("dropLabel")}
                    onDragOver={(event) => {
                        event.preventDefault();
                        setDragging(true);
                    }}
                    onDragLeave={() => setDragging(false)}
                    onDrop={onDrop}
                    className={cn(
                        "grid justify-items-center gap-3 rounded-md border border-dashed p-6 text-center",
                        dragging ? "border-primary bg-primary-soft" : "border-border bg-surface-2",
                    )}
                >
                    <p className="text-sm text-ink">{isVersion ? t("dropVersion") : t("drop")}</p>
                    <Button type="button" variant="outline" onClick={() => input.current?.click()}>
                        {t("choose")}
                    </Button>
                    <p className="text-xs text-ink-2">{t("hint")}</p>
                    <input
                        ref={input}
                        hidden
                        type="file"
                        multiple={!isVersion}
                        accept={ACCEPT}
                        onChange={(event) => {
                            add(event.target.files);
                            // The same file can be chosen again after it was removed.
                            event.target.value = "";
                        }}
                    />
                </div>
                {entries.length > 0 ? (
                    <ul aria-label={t("listLabel")} className="grid gap-3">
                        {entries.map((entry) => (
                            <UploadItem
                                key={entry.key}
                                entry={entry}
                                emptyType={isVersion ? t("sameAsPrevious") : t("autoDetect")}
                                isAdmin={isAdmin}
                                onChange={(fields) => patch(entry.key, { fields })}
                                onRemove={() =>
                                    setEntries((current) =>
                                        current.filter((e) => e.key !== entry.key),
                                    )
                                }
                            />
                        ))}
                    </ul>
                ) : null}
                {waiting || busy ? (
                    <Button
                        type="button"
                        disabled={busy}
                        onClick={() => void submit()}
                        className="w-full md:w-fit"
                    >
                        {busy ? t("uploading") : t("submit")}
                    </Button>
                ) : null}
            </CardContent>
        </Card>
    );
}
