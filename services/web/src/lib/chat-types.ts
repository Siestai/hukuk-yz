import type { components } from "@hukuk/web-core/api/schema";

type Schemas = components["schemas"];

export type Answer = Schemas["Answer"];
export type CaseFacts = Schemas["CaseFacts"];
export type Fact = Schemas["Fact"];
export type CitationRef = Schemas["CitationRef"];
export type Clarification = Schemas["Clarification"];
export type ClarificationAnswer = Schemas["ClarificationAnswer"];
export type ClarificationQuestion = Schemas["ClarificationQuestion"];
export type Conversation = Schemas["Conversation"];
export type ConversationDetail = Schemas["ConversationDetail"];
export type FeedbackIn = Schemas["FeedbackIn"];
export type HoldingRow = Schemas["HoldingRow"];
export type MessageRequest = Schemas["MessageRequest"];
export type Turn = Schemas["Turn"];
export type ChatMode = NonNullable<MessageRequest["mode"]>;
/** What the user sends: a question, answers to the open questions, or the choice to skip them. */
export type Reply = {
    text?: string;
    clarification_answers?: ClarificationAnswer[];
    skip?: boolean;
};

/**
 * One event of the message stream. The OpenAPI document does not describe the `text/event-stream`
 * body, so only this envelope is written here; every payload is a generated schema.
 */
export type ChatEvent =
    | { type: "step"; node: string; label: string }
    | { type: "facts"; facts: CaseFacts }
    | { type: "clarification"; clarification: Clarification }
    | { type: "answer"; answer: Answer }
    | { type: "error"; code: string; params?: Record<string, string | number> }
    | { type: "done"; turn_id?: string | null; trace_id?: string | null };
