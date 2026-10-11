"use client";

import { Button } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { createApiClient } from "@/lib/api/client";
import { postFileAction } from "@/lib/api/files-client";
import { ApiFailure } from "@/lib/api/review-client";
import { useErrorMessage } from "@/lib/use-error-message";

/** Archive or restore a file, and queue it for another scan (admin). */
export function FileAdminActions({ fileId, archived }: { fileId: string; archived: boolean }) {
    const t = useTranslations("files.detail.actions");
    const errorMessage = useErrorMessage();
    const router = useRouter();
    const [busy, setBusy] = useState(false);
    const [failure, setFailure] = useState<string>();

    async function run(action: "archive" | "unarchive" | "rescan") {
        setBusy(true);
        setFailure(undefined);
        try {
            await postFileAction(createApiClient(), fileId, action);
            router.refresh();
        } catch (error) {
            setFailure(errorMessage(error instanceof ApiFailure ? error.code : undefined));
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="grid gap-2">
            <div className="flex flex-wrap gap-2">
                <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void run(archived ? "unarchive" : "archive")}
                >
                    {archived ? t("unarchive") : t("archive")}
                </Button>
                <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => void run("rescan")}
                >
                    {t("rescan")}
                </Button>
            </div>
            {failure ? (
                <p role="alert" className="text-sm text-low">
                    {failure}
                </p>
            ) : null}
        </div>
    );
}
