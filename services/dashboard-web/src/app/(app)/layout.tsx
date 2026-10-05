import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";
import { UpstreamUnavailableError } from "@/lib/api/errors";
import { getReviewSummary } from "@/lib/api/review";
import { createServerApi } from "@/lib/api/server";

export default async function AppLayout({ children }: { children: ReactNode }) {
    const api = await createServerApi();
    const me = await api.GET("/auth/me").catch((cause: unknown) => {
        throw new UpstreamUnavailableError(`GET /auth/me failed: ${String(cause)}`);
    });
    // The cookie exists but the API does not accept it: drop it and sign in again.
    if (me.response.status === 401) redirect("/oturum-sonu");
    if (me.response.status >= 500) {
        throw new UpstreamUnavailableError(`GET /auth/me answered ${me.response.status}`);
    }
    if (!me.data) throw new Error(`GET /auth/me failed with ${me.response.status}`);

    // The badge is a courtesy: no count is shown rather than failing the page.
    const summary = await getReviewSummary().catch(() => null);
    const pending = summary?.data
        ? Object.values(summary.data.by_band).reduce((sum, n) => sum + n, 0)
        : null;

    return (
        <AppShell user={me.data} pending={pending}>
            {children}
        </AppShell>
    );
}
