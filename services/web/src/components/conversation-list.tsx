"use client";

import { Button, cn } from "@hukuk/ui";
import { LogoutButton } from "@hukuk/web-core/components/logout-button";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";

import type { Conversation } from "@/lib/chat-types";

/** The conversations of the signed-in user, newest first: title and date, and "Yeni soru". */
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
                variant="outline"
                className="justify-start font-semibold text-primary"
                onClick={() => {
                    onNew();
                    onNavigate();
                }}
            >
                <span aria-hidden="true">{"+"}</span>
                {t("new")}
            </Button>
            <nav aria-label={t("title")} className="min-h-0 flex-1 overflow-y-auto">
                {conversations.length === 0 ? (
                    <p className="px-3 text-sm text-ink-3">{t("empty")}</p>
                ) : (
                    <ul className="grid gap-1">
                        {conversations.map((conversation) => (
                            <li key={conversation.id}>
                                <Link
                                    href={`/konusmalar/${conversation.id}`}
                                    onClick={onNavigate}
                                    aria-current={conversation.id === activeId ? "page" : undefined}
                                    className={cn(
                                        "grid min-h-11 gap-0.5 rounded-md px-3 py-2 text-sm focus-visible:outline-2 focus-visible:outline-ring",
                                        conversation.id === activeId
                                            ? "bg-primary-soft font-semibold text-primary"
                                            : "text-ink-2 hover:bg-primary-soft",
                                    )}
                                >
                                    <span className="wrap-anywhere">
                                        {conversation.title || t("untitled")}
                                    </span>
                                    <span className="text-xs font-normal text-ink-3">
                                        {format.dateTime(new Date(conversation.updated_at), "date")}
                                    </span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                )}
            </nav>
            <LogoutButton label={t("logout")} />
        </div>
    );
}
