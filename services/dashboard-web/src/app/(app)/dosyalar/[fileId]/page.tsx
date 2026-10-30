import { Badge } from "@hukuk/ui";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ApprovalPanel } from "@/components/files/approval-panel";
import { FileAdminActions } from "@/components/files/file-admin-actions";
import { FileDetailsCard } from "@/components/files/file-details-card";
import { FileText } from "@/components/files/file-text";
import { FileViewer } from "@/components/files/file-viewer";
import { NewVersion } from "@/components/files/new-version";
import { ReviewBadge } from "@/components/files/review-badge";
import { ScanBadge } from "@/components/files/scan-badge";
import { ScanRefresh } from "@/components/files/scan-refresh";
import { ScanResultCard } from "@/components/files/scan-result-card";
import { VersionHistory } from "@/components/files/version-history";
import { getFileNames } from "@/lib/api/files";
import { getMe } from "@hukuk/web-core/api/me";
import { createServerApi } from "@hukuk/web-core/api/server";
import { settle } from "@hukuk/web-core/api/settle";
import { readMatches } from "@/lib/file-suggestions";
import { ACTIVE_SCANS, fileHref, readScan } from "@/lib/files";
import { isUuid } from "@/lib/uuid";

export default async function FilePage({ params }: { params: Promise<{ fileId: string }> }) {
    const { fileId } = await params;
    if (!isUuid(fileId)) notFound();
    const t = await getTranslations("files.detail");
    const api = await createServerApi();
    const [result, me] = await Promise.all([
        settle(
            api.GET("/files/{file_id}", { params: { path: { file_id: fileId } } }),
            "GET /files/{id}",
        ),
        getMe(),
    ]);
    if (result.error) {
        if (result.error.code === "file_not_found") notFound();
        throw new Error(`GET /files/{id} answered ${result.error.code ?? "an error"}`);
    }
    const file = result.data;
    const newest = file.versions.at(-1);
    const isAdmin = me.role === "admin";
    const canAddVersion = newest?.id === file.id && file.archived_at === null;
    const pending = file.review_status === "pending";
    const matches = readMatches(file.matches);
    const names = pending
        ? await getFileNames([
              ...new Set([
                  ...(matches.previous ? [matches.previous.fileId] : []),
                  ...matches.similar.map((entry) => entry.fileId),
              ]),
          ])
        : {};

    return (
        <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
            <ScanRefresh active={ACTIVE_SCANS.includes(file.scan_status)} />
            <header className="grid gap-3">
                <Link
                    href="/dosyalar"
                    className="inline-flex w-fit items-center text-sm text-primary hover:underline pointer-coarse:min-h-11"
                >
                    {t("back")}
                </Link>
                <h1 className="font-serif text-xl wrap-anywhere text-ink md:text-2xl">
                    {file.original_name ?? t("unnamed")}
                </h1>
                <div className="flex flex-wrap items-center gap-2">
                    <ReviewBadge status={file.review_status} />
                    <ScanBadge status={file.scan_status} />
                    {file.archived_at ? <Badge variant="outline">{t("archived")}</Badge> : null}
                </div>
                {newest && newest.id !== file.id ? (
                    <p className="text-sm text-ink-2">
                        {t("olderVersion")}{" "}
                        <Link href={fileHref(newest.id)} className="text-primary underline">
                            {t("openNewest")}
                        </Link>
                    </p>
                ) : null}
            </header>
            {pending ? (
                <ApprovalPanel
                    key={file.id}
                    file={file}
                    names={names}
                    canDelete={isAdmin || file.uploaded_by_id === me.id}
                />
            ) : null}
            <FileViewer fileId={file.id} pdf={file.detected_type === "pdf"} />
            {readScan(file.scan_result).hasText ? <FileText fileId={file.id} /> : null}
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <FileDetailsCard file={file} />
                <ScanResultCard file={file} />
            </div>
            {canAddVersion ? <NewVersion fileId={file.id} isAdmin={isAdmin} /> : null}
            <VersionHistory versions={file.versions} currentId={file.id} />
            {isAdmin ? (
                <FileAdminActions
                    fileId={file.id}
                    archived={file.archived_at !== null}
                    approved={!pending}
                />
            ) : null}
        </main>
    );
}
