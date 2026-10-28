import { notFound } from "next/navigation";

import { ChatApp } from "@/components/chat-app";
import { loadChat } from "@/lib/chat-data";

export default async function ConversationPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    const { conversations, detail, missing } = await loadChat(id);
    if (missing || !detail) notFound();
    return <ChatApp key={detail.id} detail={detail} conversations={conversations} />;
}
