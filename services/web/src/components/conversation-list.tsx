"use client";

import { Button, cn } from "@hukuk/ui";
import { LogoutButton } from "@hukuk/web-core/components/logout-button";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import type { Conversation } from "@/lib/chat-types";

/**
 * The conversations of the signed-in user, newest first: title and date, and "Yeni soru". It sits
 * on the navy sidebar and drawer, so it paints with the inverse tokens.
 */
export function ConversationList({
    conversations,
    activeId,
    onNew,
    onNavigate,
}: {
    conversations: Conversation[];
    activeId: string | null;
    onNew: () => void;
    /** Called after a link is followed (the drawer closes). */
    onNavigate: () => void;
}) {
    const t = useTranslations("conversations");
    const format = useFormatter();
    return (
        <div className="flex min-h-0 flex-1 flex-col gap-4">
            <Button
                type="button"
                size="lg"
                className="min-h-12 w-full text-base font-semibold"
                onClick={() => {
                    onNew();
                    onNavigate();
                }}
            >
                <span aria-hidden="true">{"+"}</span>
                {t("new")}
            </Button>
            <nav aria-label={t("title")} className="min-h-0 flex-1 overflow-y-auto">
                <p aria-hidden="true" className="mx-2 mb-2 text-xs font-semibold text-ink-inv-2">
                    {t("title")}
                </p>
                {conversations.length === 0 ? (
                    <p className="px-2 py-3 text-sm text-ink-inv-2">{t("empty")}</p>
                ) : (
                    <ul className="grid gap-1">
                        {conversations.map((conversation) => (
                            <li key={conversation.id}>
                                <Link
                                    href={`/konusmalar/${conversation.id}`}
                                    onClick={onNavigate}
                                    aria-current={conversation.id === activeId ? "page" : undefined}
                                    className={cn(
                                        "grid min-h-12 gap-0.5 rounded-md border px-3 py-3 text-sm font-semibold leading-snug text-ink-inv hover:bg-navy-2 focus-visible:outline-2 focus-visible:outline-ring",
                                        conversation.id === activeId
                                            ? "border-navy-2 bg-navy-2"
                                            : "border-transparent",
                                    )}
                                >
                                    <span className="wrap-anywhere">
                                        {conversation.title || t("untitled")}
                                    </span>
                                    <span className="text-xs font-normal text-ink-inv-2">
                                        {format.dateTime(new Date(conversation.updated_at), "date")}
                                    </span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                )}
            </nav>
            <LogoutButton
                label={t("logout")}
                variant="inverse"
                className="min-h-12 w-full text-base font-semibold"
            />
        </div>
    );
}
