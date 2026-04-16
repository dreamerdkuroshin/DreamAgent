import { Router, type IRouter } from "express";
import { db } from "@workspace/db";
import { agentsTable, tasksTable, conversationsTable } from "@workspace/db";
import { eq, count } from "drizzle-orm";

const router: IRouter = Router();

router.get("/stats", async (_req, res) => {
  const [agentCount] = await db.select({ count: count() }).from(agentsTable);
  const [activeAgentCount] = await db
    .select({ count: count() })
    .from(agentsTable)
    .where(eq(agentsTable.status, "active"));
  const [taskCount] = await db.select({ count: count() }).from(tasksTable);
  const [completedTaskCount] = await db
    .select({ count: count() })
    .from(tasksTable)
    .where(eq(tasksTable.status, "completed"));
  const [failedTaskCount] = await db
    .select({ count: count() })
    .from(tasksTable)
    .where(eq(tasksTable.status, "failed"));
  const [pendingTaskCount] = await db
    .select({ count: count() })
    .from(tasksTable)
    .where(eq(tasksTable.status, "pending"));
  const [convCount] = await db.select({ count: count() }).from(conversationsTable);

  let swarmMetrics = { total_runs: 0, success_rate: 0, avg_duration: 0 };
  try {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";
    const metricsRes = await fetch(`${backendUrl}/api/swarm/metrics`);
    if (metricsRes.ok) {
      swarmMetrics = await metricsRes.json() as any;
    } else {
      console.error(`SI Engine metrics failed with status: ${metricsRes.status} ${metricsRes.statusText}`);
    }
  } catch (e) {
    console.error(`SI Engine unreachable for metrics at ${process.env.BACKEND_URL || "http://localhost:8001"}:`, e instanceof Error ? e.message : e);
  }

  res.json({
    totalAgents: Number(agentCount?.count ?? 0),
    activeAgents: Number(activeAgentCount?.count ?? 0),
    totalTasks: Number(taskCount?.count ?? 0),
    completedTasks: Number(completedTaskCount?.count ?? 0),
    failedTasks: Number(failedTaskCount?.count ?? 0),
    pendingTasks: Number(pendingTaskCount?.count ?? 0),
    totalConversations: Number(convCount?.count ?? 0),
    ...swarmMetrics
  });
});

export default router;
