import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { agentsTable, tasksTable, conversationsTable } from "@workspace/db";
import { eq, count } from "drizzle-orm";
import {
  CreateAgentBody,
  UpdateAgentBody,
  GetAgentParams,
  UpdateAgentParams,
  DeleteAgentParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

router.get("/agents", async (_req, res) => {
  const agents = await db.select().from(agentsTable);
  const result = await Promise.all(
    agents.map(async (agent: any) => {
      const [taskResult] = await db
        .select({ count: count() })
        .from(tasksTable)
        .where(eq(tasksTable.agentId, agent.id));
      const [convResult] = await db
        .select({ count: count() })
        .from(conversationsTable)
        .where(eq(conversationsTable.agentId, agent.id));
      return {
        ...agent,
        taskCount: Number(taskResult?.count ?? 0),
        conversationCount: Number(convResult?.count ?? 0),
      };
    })
  );
  res.json(result);
});

router.post("/agents", async (req, res) => {
  const body = CreateAgentBody.parse(req.body);
  const [agent] = await db
    .insert(agentsTable)
    .values({ ...body, status: "idle" })
    .returning();
  res.status(201).json({ ...agent, taskCount: 0, conversationCount: 0 });
});

router.get("/agents/:id", async (req, res) => {
  const { id } = GetAgentParams.parse({ id: Number(req.params.id) });
  const [agent] = await db
    .select()
    .from(agentsTable)
    .where(eq(agentsTable.id, id));
  if (!agent) {
    res.status(404).json({ error: "Agent not found" });
    return;
  }
  const [taskResult] = await db
    .select({ count: count() })
    .from(tasksTable)
    .where(eq(tasksTable.agentId, id));
  const [convResult] = await db
    .select({ count: count() })
    .from(conversationsTable)
    .where(eq(conversationsTable.agentId, id));
  res.json({
    ...agent,
    taskCount: Number(taskResult?.count ?? 0),
    conversationCount: Number(convResult?.count ?? 0),
  });
});

router.put("/agents/:id", async (req, res) => {
  const { id } = UpdateAgentParams.parse({ id: Number(req.params.id) });
  const body = UpdateAgentBody.parse(req.body);
  const [agent] = await db
    .update(agentsTable)
    .set({ ...body, updatedAt: new Date() })
    .where(eq(agentsTable.id, id))
    .returning();
  if (!agent) {
    res.status(404).json({ error: "Agent not found" });
    return;
  }
  const [taskResult] = await db
    .select({ count: count() })
    .from(tasksTable)
    .where(eq(tasksTable.agentId, id));
  const [convResult] = await db
    .select({ count: count() })
    .from(conversationsTable)
    .where(eq(conversationsTable.agentId, id));
  res.json({
    ...agent,
    taskCount: Number(taskResult?.count ?? 0),
    conversationCount: Number(convResult?.count ?? 0),
  });
});

router.delete("/agents/:id", async (req, res) => {
  const { id } = DeleteAgentParams.parse({ id: Number(req.params.id) });
  await db.delete(agentsTable).where(eq(agentsTable.id, id));
  res.status(204).send();
});

export default router;
