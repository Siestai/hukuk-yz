"use client";

import { Button } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { createApiClient } from "@/lib/api/client";
import { useErrorMessage } from "@/lib/use-error-message";

export function LogoutButton() {
    const t = useTranslations("nav");
    const errorMessage = useErrorMessage();
    const router = useRouter();
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    async function logout() {
        setPending(true);
        setError(null);
        try {
            // The API takes an unsafe request only as JSON (cross-site forms cannot send that), and
            // this one has no body to make the client add the header.
            const { response } = await createApiClient().POST("/auth/logout", {
                headers: { "Content-Type": "application/json" },
            });
            // 401: the session is already gone, which is what the user wanted.
            if (response.ok || response.status === 401) {
                router.replace("/giris");
                return;
            }
            setError(errorMessage(undefined));
        } catch {
            setError(errorMessage("upstream_unavailable"));
        }
        setPending(false);
    }

    return (
        <div className="grid gap-2">
            <Button variant="outline" size="sm" onClick={logout} disabled={pending}>
                {t("logout")}
            </Button>
            <div role="alert">{error ? <p className="text-xs text-low">{error}</p> : null}</div>
        </div>
    );
}
