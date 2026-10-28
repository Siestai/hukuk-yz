"use client";

import { Button } from "@hukuk/ui";
import { useTranslations } from "next-intl";
import { useId, useState } from "react";

import { createApiClient } from "@hukuk/web-core/api/client";
import { getFileText } from "@/lib/api/files-client";
import { ApiFailure } from "@hukuk/web-core/api/unwrap";

type State =
    { kind: "closed" } | { kind: "loading" } | { kind: "shown"; text: string } | { kind: "failed" };

/** "Metni gör": the text the scan extracted, fetched when it is first opened. It is stored data, shown as it is. */
export function FileText({ fileId }: { fileId: string }) {
    const t = useTranslations("files.detail.text");
    const [state, setState] = useState<State>({ kind: "closed" });
    const region = useId();

    async function toggle() {
        if (state.kind !== "closed" && state.kind !== "failed") {
            setState({ kind: "closed" });
            return;
        }
        setState({ kind: "loading" });
        try {
            setState({ kind: "shown", text: await getFileText(createApiClient(), fileId) });
        } catch (error) {
            if (!(error instanceof ApiFailure)) throw error;
            setState({ kind: "failed" });
        }
    }

    return (
        <section className="grid gap-3">
            <Button
                type="button"
                variant="outline"
                className="w-full md:w-fit"
                aria-expanded={state.kind === "shown" || state.kind === "loading"}
                aria-controls={region}
                onClick={() => void toggle()}
            >
                {state.kind === "shown" ? t("hide") : t("show")}
            </Button>
            <div id={region} aria-live="polite">
                {state.kind === "loading" ? (
                    <p className="text-sm text-ink-2">{t("loading")}</p>
                ) : null}
                {state.kind === "failed" ? (
                    <p role="alert" className="text-sm text-low">
                        {t("failed")}
                    </p>
                ) : null}
                {state.kind === "shown" ? (
                    state.text.trim() === "" ? (
                        <p className="text-sm text-ink-2">{t("empty")}</p>
                    ) : (
                        <article
                            aria-label={t("label")}
                            className="rounded-md border border-border bg-surface p-4 font-serif text-base wrap-anywhere whitespace-pre-wrap text-ink"
                        >
                            {state.text}
                        </article>
                    )
                ) : null}
            </div>
        </section>
    );
}
