"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { UploadPanel } from "./upload-panel";

/** "Yeni sürüm yükle": opens the upload panel for the next version of this file. */
export function NewVersion({ fileId, isAdmin }: { fileId: string; isAdmin: boolean }) {
    const t = useTranslations("files.detail");
    const [open, setOpen] = useState(false);
    const panel = useId();

    return (
        <div className="grid gap-4">
            <Button
                type="button"
                variant="outline"
                className="w-full md:w-fit"
                aria-expanded={open}
                aria-controls={panel}
                onClick={() => setOpen((value) => !value)}
            >
                {t("newVersion")}
            </Button>
            <div id={panel} hidden={!open}>
                {open ? (
                    <UploadPanel target={{ kind: "version", fileId }} isAdmin={isAdmin} />
                ) : null}
            </div>
        </div>
    );
}
