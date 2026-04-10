import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { conversationsTable, messagesTable, agentsTable } from "@workspace/db";
import { eq, count, desc } from "drizzle-orm";
import {
  CreateConversationBody,
  ListConversationsQueryParams,
  ListMessagesParams,
  SendMessageBody,
  SendMessageParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

const AI_RESPONSES = [
  "I've analyzed your request and here's what I found: the data suggests a strong correlation between your query parameters.",
  "Processing complete. Based on my analysis, I recommend the following approach to optimize your workflow.",
  "Understood. I'll execute this task with high priority. Initial analysis shows promising results.",
  "I've completed the analysis. The patterns in the data indicate a clear path forward for your goals.",
  "Task acknowledged. I'm running multi-step reasoning to provide you the most accurate response possible.",
  "Excellent question. Let me break this down into actionable steps for you.",
  "I've cross-referenced multiple data sources and here's my synthesized conclusion.",
  "Based on my training and current context, here's a comprehensive response to your query.",
];

function getAiResponse(): string {
  return AI_RESPONSES[Math.floor(Math.random() * AI_RESPONSES.length)];
}

router.get("/conversations", async (req, res) => {
  const query = ListConversationsQueryParams.parse({
    agentId: req.query.agentId ? Number(req.query.agentId) : undefined,
  });

  const conversations = await db
    .select({
      id: conversationsTable.id,
      agentId: conversationsTable.agentId,
      agentName: agentsTable.name,
      title: conversationsTable.title,
      createdAt: conversationsTable.createdAt,
      updatedAt: conversationsTable.updatedAt,
    })
    .from(conversationsTable)
    .innerJoin(agentsTable, eq(conversationsTable.agentId, agentsTable.id))
    .where(query.agentId ? eq(conversationsTable.agentId, query.agentId) : undefined)
    .orderBy(desc(conversationsTable.updatedAt));

  const result = await Promise.all(
    conversations.map(async (conv: any) => {
      const [msgCount] = await db
        .select({ count: count() })
        .from(messagesTable)
        .where(eq(messagesTable.conversationId, conv.id));
      const [lastMsg] = await db
        .select({ content: messagesTable.content })
        .from(messagesTable)
        .where(eq(messagesTable.conversationId, conv.id))
        .orderBy(desc(messagesTable.createdAt))
        .limit(1);
      return {
        ...conv,
        messageCount: Number(msgCount?.count ?? 0),
        lastMessage: lastMsg?.content ?? null,
      };
    })
  );

  res.json(result);
});

router.post("/conversations", async (req, res) => {
  const body = CreateConversationBody.parse(req.body);
  const [conversation] = await db
    .insert(conversationsTable)
    .values(body)
    .returning();

  const [agent] = await db
    .select({ name: agentsTable.name })
    .from(agentsTable)
    .where(eq(agentsTable.id, body.agentId));

  res.status(201).json({
    ...conversation,
    agentName: agent?.name ?? "Unknown",
    messageCount: 0,
    lastMessage: null,
  });
});

router.get("/conversations/:id/messages", async (req, res) => {
  const { id } = ListMessagesParams.parse({ id: Number(req.params.id) });
  const messages = await db
    .select()
    .from(messagesTable)
    .where(eq(messagesTable.conversationId, id))
    .orderBy(messagesTable.createdAt);
  res.json(messages);
});

router.post("/conversations/:id/messages", async (req, res) => {
  const { id } = SendMessageParams.parse({ id: Number(req.params.id) });
  const body = SendMessageBody.parse(req.body);

  // 1. Save user message to DB
  const [userMsg] = await db
    .insert(messagesTable)
    .values({ conversationId: id, role: "user", content: body.content })
    .returning();

  let aiContent: string;
  try {
    // 2. Call the Python Swarm Backend
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    const backendResponse = await fetch(`${backendUrl}/swarm/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task: body.content, mode: body.mode }),
    });

    if (!backendResponse.ok) {
      throw new Error(`Backend error: ${backendResponse.status} ${backendResponse.statusText}`);
    }

    const data = await backendResponse.json() as any;
    aiContent = data.result || "Swarm: No response generated.";
  } catch (error) {
    console.error(`Failed to connect to Python Swarm at ${process.env.BACKEND_URL || "http://localhost:8001"}:`, error instanceof Error ? error.message : error);
    aiContent = "Error: Could not reach the DreamAgent Intelligence Swarm. Please ensure the backend is running.";
  }

  // 3. Save assistant message to DB
  const [assistantMsg] = await db
    .insert(messagesTable)
    .values({ conversationId: id, role: "assistant", content: aiContent })
    .returning();

  await db
    .update(conversationsTable)
    .set({ updatedAt: new Date() })
    .where(eq(conversationsTable.id, id));

  res.status(201).json({ userMessage: userMsg, assistantMessage: assistantMsg });
});

export default router;
