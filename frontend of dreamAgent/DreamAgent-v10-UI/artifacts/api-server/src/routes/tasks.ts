import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { tasksTable, agentsTable } from "@workspace/db";
import { eq, and } from "drizzle-orm";
import {
  CreateTaskBody,
  UpdateTaskBody,
  ListTasksQueryParams,
  GetTaskParams,
  UpdateTaskParams,
} from "@workspace/api-zod";

const router: IRouter = Router();

router.get("/tasks", async (req, res) => {
  const query = ListTasksQueryParams.parse({
    agentId: req.query.agentId ? Number(req.query.agentId) : undefined,
    status: req.query.status,
  });

  const tasks = await db
    .select({
      id: tasksTable.id,
      agentId: tasksTable.agentId,
      agentName: agentsTable.name,
      title: tasksTable.title,
      description: tasksTable.description,
      status: tasksTable.status,
      priority: tasksTable.priority,
      result: tasksTable.result,
      createdAt: tasksTable.createdAt,
      updatedAt: tasksTable.updatedAt,
      completedAt: tasksTable.completedAt,
    })
    .from(tasksTable)
    .innerJoin(agentsTable, eq(tasksTable.agentId, agentsTable.id))
    .where(
      and(
        query.agentId ? eq(tasksTable.agentId, query.agentId) : undefined,
        query.status ? eq(tasksTable.status, query.status) : undefined
      )
    );

  res.json(tasks);
});

router.post("/tasks", async (req, res) => {
  const body = CreateTaskBody.parse(req.body);
  const [task] = await db
    .insert(tasksTable)
    .values({ ...body, status: "pending" })
    .returning();

  const [agent] = await db
    .select({ name: agentsTable.name })
    .from(agentsTable)
    .where(eq(agentsTable.id, body.agentId));

  res.status(201).json({ ...task, agentName: agent?.name ?? "Unknown" });
});

router.get("/tasks/:id", async (req, res) => {
  const { id } = GetTaskParams.parse({ id: Number(req.params.id) });
  const [task] = await db
    .select({
      id: tasksTable.id,
      agentId: tasksTable.agentId,
      agentName: agentsTable.name,
      title: tasksTable.title,
      description: tasksTable.description,
      status: tasksTable.status,
      priority: tasksTable.priority,
      result: tasksTable.result,
      createdAt: tasksTable.createdAt,
      updatedAt: tasksTable.updatedAt,
      completedAt: tasksTable.completedAt,
    })
    .from(tasksTable)
    .innerJoin(agentsTable, eq(tasksTable.agentId, agentsTable.id))
    .where(eq(tasksTable.id, id));

  if (!task) {
    res.status(404).json({ error: "Task not found" });
    return;
  }
  res.json(task);
});

router.put("/tasks/:id", async (req, res) => {
  const { id } = UpdateTaskParams.parse({ id: Number(req.params.id) });
  const body = UpdateTaskBody.parse(req.body);

  const updateData: Partial<typeof tasksTable.$inferInsert> = {
    ...body,
    updatedAt: new Date(),
  };

  if (body.status === "completed" || body.status === "failed") {
    updateData.completedAt = new Date();
  }

  const [task] = await db
    .update(tasksTable)
    .set(updateData)
    .where(eq(tasksTable.id, id))
    .returning();

  if (!task) {
    res.status(404).json({ error: "Task not found" });
    return;
  }

  const [agent] = await db
    .select({ name: agentsTable.name })
    .from(agentsTable)
    .where(eq(agentsTable.id, task.agentId));

  res.json({ ...task, agentName: agent?.name ?? "Unknown" });
});

export default router;
