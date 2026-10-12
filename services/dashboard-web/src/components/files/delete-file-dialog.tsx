"use client";

import { Button, Dialog, DialogActions } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState, type RefObject } from "react";

import { createApiClient } from "@/lib/api/client";
import { deleteFile } from "@/lib/api/files-client";
import { ApiFailure } from "@/lib/api/review-client";
import { useErrorMessage } from "@/lib/use-error-message";

/** Asks before a pending file is deleted; on success the list is shown, on refusal the reason. */
export function DeleteFileDialog({
    open,
    onClose,
    fileId,
    name,
    returnFocusTo,
}: {
    open: boolean;
    onClose: () => void;
    fileId: string;
    name: string;
    returnFocusTo: RefObject<HTMLElement | null>;
}) {
    const t = useTranslations("files.detail.approve.deleteDialog");
    const errorMessage = useErrorMessage();
    const router = useRouter();
    const [busy, setBusy] = useState(false);
    const [failure, setFailure] = useState<string>();

    function close() {
        setFailure(undefined);
        onClose();
    }

    async function remove() {
        setBusy(true);
        setFailure(undefined);
        try {
            await deleteFile(createApiClient(), fileId);
            router.push("/dosyalar");
        } catch (error) {
            setFailure(errorMessage(error instanceof ApiFailure ? error.code : undefined));
            setBusy(false);
        }
    }

    return (
        <Dialog
            open={open}
            onClose={close}
            title={t("title")}
            dismissible={!busy}
            returnFocusTo={returnFocusTo}
        >
            <p className="text-sm wrap-anywhere text-ink">{t("body", { name })}</p>
            {failure ? (
                <p role="alert" className="text-sm text-low">
                    {failure}
                </p>
            ) : null}
            <DialogActions>
                <Button type="button" variant="outline" disabled={busy} onClick={close}>
                    {t("cancel")}
                </Button>
                <Button
                    type="button"
                    variant="destructive"
                    disabled={busy}
                    onClick={() => void remove()}
                >
                    {busy ? t("deleting") : t("confirm")}
                </Button>
            </DialogActions>
        </Dialog>
    );
}
