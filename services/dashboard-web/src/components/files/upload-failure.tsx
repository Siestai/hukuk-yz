"use client";

import { Button } from "@hukuk/ui";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { createApiClient } from "@hukuk/web-core/api/client";
import { postFileAction } from "@/lib/api/files-client";
import { ApiFailure } from "@hukuk/web-core/api/unwrap";
import { fileHref } from "@/lib/files";
import { useErrorMessage } from "@hukuk/web-core/hooks/use-error-message";
import { isUuid } from "@/lib/uuid";

const linkClass =
    "inline-flex items-center text-sm font-medium text-primary underline pointer-coarse:min-h-11";

/**
 * Why an upload was refused. A duplicate points at the record that already holds the file; when
 * that record is in the archive, an admin can take it out right here.
 */
export function UploadFailure({
    code,
    params,
    isAdmin,
}: {
    code: string | undefined;
    params: Record<string, unknown>;
    isAdmin: boolean;
}) {
    const t = useTranslations("files.upload");
    const errorMessage = useErrorMessage();
    const [unarchived, setUnarchived] = useState(false);
    const [busy, setBusy] = useState(false);
    const [failure, setFailure] = useState<string>();

    const existing =
        typeof params.file_id === "string" && isUuid(params.file_id) ? params.file_id : null;
    if (code !== "duplicate_file" || !existing) {
        return (
            <p role="alert" className="text-sm text-low">
                {errorMessage(code, params)}
            </p>
        );
    }
    const archived = params.archived === true && !unarchived;

    async function unarchive(id: string) {
        setBusy(true);
        setFailure(undefined);
        try {
            await postFileAction(createApiClient(), id, "unarchive");
            setUnarchived(true);
        } catch (error) {
            setFailure(errorMessage(error instanceof ApiFailure ? error.code : undefined));
        } finally {
            setBusy(false);
        }
    }

    return (
        <div role="alert" className="grid gap-2 text-sm">
            <p className="text-ink">{archived ? t("duplicateArchived") : t("duplicate")}</p>
            {unarchived ? <p className="text-ink-2">{t("unarchived")}</p> : null}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
                <Link href={fileHref(existing)} className={linkClass}>
                    {t("openExisting")}
                </Link>
                {archived && isAdmin ? (
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={busy}
                        onClick={() => void unarchive(existing)}
                    >
                        {t("unarchive")}
                    </Button>
                ) : null}
            </div>
            {failure ? <p className="text-low">{failure}</p> : null}
        </div>
    );
}
