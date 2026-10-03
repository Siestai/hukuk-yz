"use client";

import { Button, Input, Label } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { type FormEvent, useRef, useState } from "react";

import { createApiClient } from "@/lib/api/client";
import { apiError } from "@/lib/api/errors";
import { useErrorMessage } from "@/lib/use-error-message";

type Invalid = { email: boolean; password: boolean };

const ERROR_ID = "login-error";
// Only these say something is wrong with the input; a rate limit or an outage is not the fields' fault.
const FIELD_ERRORS = ["unauthorized", "validation_error"];

export function LoginForm({ next }: { next: string }) {
    const t = useTranslations("login");
    const errorMessage = useErrorMessage();
    const router = useRouter();
    const emailRef = useRef<HTMLInputElement>(null);
    const passwordRef = useRef<HTMLInputElement>(null);
    const [pending, setPending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [invalid, setInvalid] = useState<Invalid>({ email: false, password: false });

    function fail(message: string, fields: Invalid) {
        setError(message);
        setInvalid(fields);
        if (fields.email) emailRef.current?.focus();
        else if (fields.password) passwordRef.current?.focus();
    }

    async function onSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        const email = emailRef.current?.value.trim() ?? "";
        const password = passwordRef.current?.value ?? "";
        if (!email || !password) {
            fail(t("required"), { email: !email, password: !password });
            return;
        }
        setPending(true);
        setError(null);
        setInvalid({ email: false, password: false });
        try {
            const { response, error: body } = await createApiClient().POST("/auth/login", {
                body: { email, password },
            });
            if (response.ok) {
                router.replace(next);
                return;
            }
            const { code, params } = apiError(body);
            const retryAfter = Number(response.headers.get("retry-after"));
            const fieldError = code !== undefined && FIELD_ERRORS.includes(code);
            fail(
                errorMessage(code, {
                    ...params,
                    ...(retryAfter > 0 ? { retry_after: retryAfter } : {}),
                }),
                { email: fieldError, password: fieldError },
            );
        } catch {
            fail(errorMessage("upstream_unavailable"), { email: false, password: false });
        }
        setPending(false);
    }

    return (
        <form onSubmit={onSubmit} noValidate className="grid gap-5" aria-busy={pending}>
            <div role="alert">
                {error ? (
                    <p id={ERROR_ID} className="rounded-md bg-low-soft px-3 py-2 text-sm text-low">
                        {error}
                    </p>
                ) : null}
            </div>
            <div className="grid gap-2">
                <Label htmlFor="email">{t("email")}</Label>
                <Input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    ref={emailRef}
                    aria-invalid={invalid.email}
                    aria-describedby={error ? ERROR_ID : undefined}
                />
            </div>
            <div className="grid gap-2">
                <Label htmlFor="password">{t("password")}</Label>
                <Input
                    id="password"
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    ref={passwordRef}
                    aria-invalid={invalid.password}
                    aria-describedby={error ? ERROR_ID : undefined}
                />
            </div>
            <Button type="submit" size="lg" disabled={pending}>
                {pending ? t("submitting") : t("submit")}
            </Button>
        </form>
    );
}
