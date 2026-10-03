import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { SideNav } from "@/components/side-nav";
import { createServerApi } from "@/lib/api/server";

export default async function AppLayout({ children }: { children: ReactNode }) {
    const api = await createServerApi();
    const me = await api.GET("/auth/me");
    // The cookie exists but the API does not accept it: drop it and sign in again.
    if (me.response.status === 401) redirect("/oturum-sonu");
    if (!me.data) throw new Error(`GET /auth/me failed with ${me.response.status}`);

    // The badge is a courtesy: no count is shown rather than failing the page.
    const summary = await api.GET("/review/decisions/summary").catch(() => null);
    const pending = summary?.data
        ? Object.values(summary.data.by_band).reduce((sum, n) => sum + n, 0)
        : null;

    return (
        <div className="flex min-h-screen">
            <SideNav user={me.data} pending={pending} />
            <div className="min-w-0 flex-1">{children}</div>
        </div>
    );
}
