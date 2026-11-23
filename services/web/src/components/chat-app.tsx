"use client";

import { cn, Dialog } from "@hukuk/ui";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import type { ChatMode, CitationRef, Conversation, ConversationDetail } from "@/lib/chat-types";
import { useChatSession } from "@/lib/use-chat-session";
import { useWide } from "@/lib/use-wide";
import { CitationViewer } from "./citation-viewer";
import { Composer } from "./composer";
import { ConversationList } from "./conversation-list";
import { ModeTabs } from "./mode-tabs";
import { HarbourMark } from "./harbour-mark";
import { hasOpenQuestions, Thread } from "./thread";
import { Wordmark } from "./wordmark";

/** Today in Türkiye's time zone, as `YYYY-MM-DD` (the Swedish locale formats dates that way). */
const localDate = () => new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Istanbul" });

/**
 * The chat screen: conversations on the left (a drawer on a phone), the thread in the middle with
 * the mode selector above it, the source panel on the right (a bottom sheet on a phone).
 */
export function ChatApp({
    detail,
    conversations,
}: {
    detail: ConversationDetail | null;
    conversations: Conversation[];
}) {
    const t = useTranslations("chat");
    const list = useTranslations("conversations");
    const router = useRouter();
    const wide = useWide();
    const session = useChatSession(detail, conversations);
    const [mode, setMode] = useState<ChatMode>("short");
    const [opened, setOpened] = useState<{ citation: CitationRef; asOf: string } | null>(null);
    const [drawer, setDrawer] = useState(false);
    const menu = useRef<HTMLButtonElement>(null);

    const { turns, live } = session;
    const answer = turns.findLast((turn) => turn.answer)?.answer ?? null;
    const title =
        session.conversations.find((c) => c.id === session.conversationId)?.title ||
        turns.findLast((turn) => turn.facts)?.facts?.title ||
        list("untitled");
    const asking = hasOpenQuestions(turns, live);

    // Reset first: from the "/" page the router keeps the same page element, so it would not remount.
    function startNew() {
        session.reset();
        setOpened(null);
        router.push("/");
    }

    const conversationList = (
        <ConversationList
            conversations={session.conversations}
            activeId={session.conversationId}
            onNew={startNew}
            onNavigate={() => setDrawer(false)}
        />
    );

    return (
        <div className="flex h-viewport overflow-hidden bg-bg">
            <aside
                data-tone="dark"
                className="hidden w-64 shrink-0 flex-col gap-6 bg-navy p-4 pb-8 text-ink-inv lg:flex xl:w-68"
            >
                <Wordmark dark className="px-1 pt-2" />
                {conversationList}
            </aside>
            <section className="flex min-w-0 flex-1 flex-col">
                <header className="flex items-center gap-3 border-b border-line px-safe-4 pt-safe-2 pb-2 lg:hidden">
                    <Wordmark className="flex-1" />
                    <button
                        ref={menu}
                        type="button"
                        aria-label={list("open")}
                        aria-haspopup="dialog"
                        onClick={() => setDrawer(true)}
                        className="lip lip-line inline-flex size-12 shrink-0 items-center justify-center rounded-md border border-input bg-surface text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                    >
                        <svg
                            aria-hidden="true"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth={2}
                            strokeLinecap="round"
                            className="size-5"
                        >
                            <path d="M4 6h16M4 12h16M4 18h16" />
                        </svg>
                    </button>
                </header>
                <div className="mx-auto flex w-full max-w-read items-center gap-4 px-safe-4 pt-3 md:px-safe-6 lg:pt-5">
                    <h1 className="wrap-anywhere sr-only truncate font-serif text-xl font-medium text-ink lg:not-sr-only lg:flex-1">
                        {title}
                    </h1>
                    {answer ? (
                        <ModeTabs mode={mode} onChange={setMode} className="w-full lg:w-80" />
                    ) : null}
                </div>
                <div className="flex-1 overflow-y-auto overscroll-contain">
                    <div className="mx-auto grid max-w-read grid-cols-1 gap-4 px-safe-4 pt-6 pb-8 md:px-safe-6 md:pb-12">
                        {turns.length === 0 && !live ? (
                            <div className="grid justify-items-center gap-4 pt-6 text-center">
                                <HarbourMark />
                                <h2 className="font-serif text-2xl font-medium tracking-tight text-ink md:text-4xl">
                                    {t("empty.title")}
                                </h2>
                                <p className="max-w-prose text-sm text-ink-2">{t("empty.hint")}</p>
                            </div>
                        ) : null}
                        <Thread
                            turns={turns}
                            live={live}
                            partial={session.partial}
                            failure={session.failure}
                            mode={mode}
                            onSend={(body) => session.send(body, mode)}
                            onRetry={session.retry}
                            onOpenCitation={(citation, asOf) =>
                                setOpened({ citation, asOf: asOf ?? localDate() })
                            }
                        />
                    </div>
                </div>
                {asking ? null : (
                    <Composer
                        disabled={session.busy}
                        onSend={(text) => session.send({ text }, mode)}
                    />
                )}
            </section>
            <aside
                aria-label={t("viewer.panel")}
                className={cn(
                    "w-80 shrink-0 overflow-y-auto border-l border-line bg-surface xl:w-110",
                    opened ? "hidden lg:block" : "hidden xl:block",
                )}
            >
                <p className="px-5 pt-5 text-sm font-semibold text-ink-2">{t("viewer.title")}</p>
                {opened && wide ? (
                    <div className="p-5 pt-3">
                        <CitationViewer citation={opened.citation} asOf={opened.asOf} />
                    </div>
                ) : (
                    <p className="px-5 pt-3 text-sm text-ink-2">{t("viewer.empty")}</p>
                )}
            </aside>
            <Dialog
                variant="drawer"
                open={drawer && !wide}
                onClose={() => setDrawer(false)}
                title={list("title")}
                closeLabel={list("close")}
                returnFocusTo={menu}
                data-tone="dark"
                className="border-navy-2 bg-navy text-ink-inv"
                closeClassName="text-ink-inv hover:bg-navy-2"
            >
                <div className="flex min-h-0 flex-col gap-6">
                    <Wordmark dark className="px-1" />
                    {conversationList}
                </div>
            </Dialog>
            <Dialog
                variant="sheet"
                open={opened !== null && !wide}
                onClose={() => setOpened(null)}
                title={t("viewer.title")}
                closeLabel={t("viewer.close")}
                className="rounded-t-card"
            >
                {opened ? <CitationViewer citation={opened.citation} asOf={opened.asOf} /> : null}
            </Dialog>
        </div>
    );
}
