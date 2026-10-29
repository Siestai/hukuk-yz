"use client";

import { Dialog, Logo } from "@hukuk/ui";
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
import { hasOpenQuestions, Thread } from "./thread";

/** Today in the user's time zone, as `YYYY-MM-DD` (the Swedish locale formats dates that way). */
const localDate = () => new Date().toLocaleDateString("sv-SE");

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
    const brand = useTranslations("brand");
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
            <aside className="hidden w-64 shrink-0 flex-col gap-4 border-r border-line bg-surface p-4 lg:flex">
                <div className="flex items-center gap-3 text-primary">
                    <Logo label={brand("logoLabel")} className="size-7" />
                    <p className="text-lg font-semibold leading-none text-ink">{brand("name")}</p>
                </div>
                {conversationList}
            </aside>
            <section className="flex min-w-0 flex-1 flex-col">
                <header className="flex flex-col gap-3 border-b border-line bg-surface pt-safe-2 pb-3 px-safe-4 md:px-safe-6 lg:flex-row lg:items-center lg:justify-between lg:pt-safe-3">
                    <div className="flex min-w-0 items-center gap-2">
                        <button
                            ref={menu}
                            type="button"
                            aria-label={list("open")}
                            aria-haspopup="dialog"
                            onClick={() => setDrawer(true)}
                            className="-ml-2 inline-flex size-9 shrink-0 items-center justify-center rounded-md text-ink hover:bg-primary-soft focus-visible:outline-2 focus-visible:outline-ring pointer-coarse:size-11 lg:hidden"
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
                        <h1 className="wrap-anywhere truncate text-lg font-semibold text-ink">
                            {title}
                        </h1>
                    </div>
                    {answer ? (
                        <ModeTabs mode={mode} onChange={setMode} className="lg:w-80" />
                    ) : null}
                </header>
                <div className="flex-1 overflow-y-auto overscroll-contain">
                    <div className="mx-auto grid max-w-3xl grid-cols-1 gap-4 p-4 px-safe-4 md:px-safe-6">
                        {turns.length === 0 && !live ? (
                            <div className="grid gap-2 py-12 text-center">
                                <h2 className="font-serif text-2xl font-semibold text-ink">
                                    {t("empty.title")}
                                </h2>
                                <p className="text-ink-2">{t("empty.hint")}</p>
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
                className="hidden w-80 shrink-0 overflow-y-auto border-l border-line bg-surface p-5 lg:block xl:w-96"
            >
                <p className="mb-2 text-sm font-medium text-ink-3">{t("viewer.title")}</p>
                {opened && wide ? (
                    <CitationViewer citation={opened.citation} asOf={opened.asOf} />
                ) : (
                    <p className="text-sm text-ink-3">{t("viewer.empty")}</p>
                )}
            </aside>
            <Dialog
                variant="drawer"
                open={drawer && !wide}
                onClose={() => setDrawer(false)}
                title={list("title")}
                closeLabel={list("close")}
                returnFocusTo={menu}
            >
                <div className="flex min-h-0 flex-col gap-4">{conversationList}</div>
            </Dialog>
            <Dialog
                variant="sheet"
                open={opened !== null && !wide}
                onClose={() => setOpened(null)}
                title={t("viewer.title")}
                closeLabel={t("viewer.close")}
            >
                {opened ? <CitationViewer citation={opened.citation} asOf={opened.asOf} /> : null}
            </Dialog>
        </div>
    );
}
