import { ChatApp } from "@/components/chat-app";
import { loadChat } from "@/lib/chat-data";

export default async function NewQuestionPage() {
    const { conversations } = await loadChat();
    return <ChatApp key="new" detail={null} conversations={conversations} />;
}
