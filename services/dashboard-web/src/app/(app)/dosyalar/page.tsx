import { Suspense } from "react";
import { getTranslations } from "next-intl/server";

import { FileFilters } from "@/components/files/file-filters";
import { FileResults } from "@/components/files/file-results";
import { FileTabs } from "@/components/files/file-tabs";
import { UploadPanel } from "@/components/files/upload-panel";
import { QueueSkeleton } from "@/components/review-queue/queue-skeleton";
import { getPendingFiles } from "@/lib/api/files";
import { getMe } from "@/lib/api/me";
import { createServerApi } from "@/lib/api/server";
import { settle } from "@/lib/api/settle";
import { fileApiQuery, parseFileParams, serializeFileParams } from "@/lib/files";

export default async function FilesPage({
    searchParams,
}: {
    searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
    const params = parseFileParams(await searchParams);
    const t = await getTranslations("files.list");
    const api = await createServerApi();
    // The list streams into the Suspense boundary below. If `getMe` throws first, nobody awaits
    // it, so its rejection must not go unhandled.
    const list = settle(
        api.GET("/files", { params: { query: fileApiQuery(params) } }),
        "GET /files",
    );
    list.catch(() => {});
    const [me, pending] = await Promise.all([getMe(), getPendingFiles()]);

    return (
        <main className="grid grid-cols-1 gap-6 p-4 md:p-6 lg:p-8">
            <header>
                <h1 className="text-xl font-semibold text-ink">{t("title")}</h1>
                <p className="mt-1 text-sm text-ink-2">{t("subtitle")}</p>
            </header>
            <UploadPanel target={{ kind: "new" }} isAdmin={me.role === "admin"} />
            <FileTabs params={params} pending={pending} />
            <FileFilters />
            <Suspense key={serializeFileParams(params).toString()} fallback={<QueueSkeleton />}>
                <FileResults params={params} list={list} />
            </Suspense>
        </main>
    );
}
