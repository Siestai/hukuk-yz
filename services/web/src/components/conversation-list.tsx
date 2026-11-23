"use client";

import { Button, cn } from "@hukuk/ui";
import { LogoutButton } from "@hukuk/web-core/components/logout-button";
import Link from "next/link";
import { useFormatter, useTranslations } from "next-intl";
import { useId } from "react";

import type { Conversation } from "@/lib/chat-types";

/**
 * The conversations of the signed-in user, pinned ones first then newest first: title, date, pin button and "Yeni soru". It sits
 * on the navy sidebar and drawer, so it paints with the inverse tokens.
 */
export function ConversationList({
    conversations,
    activeId,
    onNew,
    onPin,
    notice,
    onNavigate,
}: {
    conversations: Conversation[];
    activeId: string | null;
    onNew: () => void;
    /** Pins or unpins a conversation (at most three can be pinned). */
    onPin: (id: string, pinned: boolean) => void;
    /** Why the last pin failed, already translated. */
    notice: string | null;
    /** Called after a link is followed (the drawer closes). */
    onNavigate: () => void;
}) {
    const t = useTranslations("conversations");
    const pinned = conversations.filter((c) => c.pinned);
    const rest = conversations.filter((c) => !c.pinned);
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
                {conversations.length === 0 ? (
                    <>
                        <p className="mx-2 mb-2 text-xs font-semibold text-ink-inv-2">
                            {t("title")}
                        </p>
                        <p className="px-2 py-3 text-sm text-ink-inv-2">{t("empty")}</p>
                    </>
                ) : (
                    <div className="grid gap-4">
                        {pinned.length > 0 && (
                            <Section
                                heading={t("pinned")}
                                items={pinned}
                                activeId={activeId}
                                onPin={onPin}
                                onNavigate={onNavigate}
                            />
                        )}
                        <Section
                            heading={t("title")}
                            items={rest}
                            activeId={activeId}
                            onPin={onPin}
                            onNavigate={onNavigate}
                        />
                    </div>
                )}
            </nav>
            {notice && (
                <p role="status" className="px-2 text-sm text-ink-inv">
                    {notice}
                </p>
            )}
            <LogoutButton
                label={t("logout")}
                variant="inverse"
                className="min-h-12 w-full text-base font-semibold"
            />
        </div>
    );
}

function Section({
    heading,
    items,
    activeId,
    onPin,
    onNavigate,
}: {
    heading: string;
    items: Conversation[];
    activeId: string | null;
    onPin: (id: string, pinned: boolean) => void;
    onNavigate: () => void;
}) {
    const t = useTranslations("conversations");
    const format = useFormatter();
    const headingId = useId();
    return (
        <section aria-labelledby={headingId}>
            <p id={headingId} className="mx-2 mb-2 text-xs font-semibold text-ink-inv-2">
                {heading}
            </p>
            <ul className="grid gap-1">
                {items.map((conversation) => {
                    const title = conversation.title || t("untitled");
                    const label = conversation.pinned ? t("unpin", { title }) : t("pin", { title });
                    return (
                        <li key={conversation.id} className="group relative">
                            <Link
                                href={`/konusmalar/${conversation.id}`}
                                onClick={onNavigate}
                                aria-current={conversation.id === activeId ? "page" : undefined}
                                className={cn(
                                    "grid min-h-12 min-w-0 gap-0.5 rounded-md border py-3 pr-12 pl-3 text-sm font-semibold leading-snug text-ink-inv hover:bg-navy-2 focus-visible:outline-2 focus-visible:outline-ring",
                                    conversation.id === activeId
                                        ? "border-navy-2 bg-navy-2"
                                        : "border-transparent",
                                )}
                            >
                                <span title={title} className="truncate">
                                    {title}
                                </span>
                                <span className="text-xs font-normal text-ink-inv-2">
                                    {format.dateTime(new Date(conversation.updated_at), "date")}
                                </span>
                            </Link>
                            <button
                                type="button"
                                aria-label={label}
                                aria-pressed={conversation.pinned}
                                onClick={() => onPin(conversation.id, !conversation.pinned)}
                                className={cn(
                                    "absolute top-0 right-0 inline-flex size-11 items-center justify-center rounded-md text-ink-inv-2 hover:text-ink-inv focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:opacity-100 md:opacity-0 md:group-hover:opacity-100",
                                    conversation.pinned && "text-ink-inv md:opacity-100",
                                )}
                            >
                                <svg
                                    aria-hidden="true"
                                    viewBox="0 0 24 24"
                                    fill={conversation.pinned ? "currentColor" : "none"}
                                    stroke="currentColor"
                                    strokeWidth={2}
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    className="size-4"
                                >
                                    <path d="M12 17v5M9 3h6l-1 7 3 3H7l3-3-1-7z" />
                                </svg>
                            </button>
                        </li>
                    );
                })}
            </ul>
        </section>
    );
}
