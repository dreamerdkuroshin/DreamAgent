import { useListTasks, useListConversations } from "@workspace/api-client-react";
import { Layout } from "@/components/layout";
import { Card, Badge } from "@/components/ui-elements";
import { History as HistoryIcon, Loader2, CheckCircle, XCircle } from "lucide-react";
import { formatDate } from "@/lib/utils";

export default function Activity() {
  // Fetch completed and failed tasks for timeline
  const { data: completedTasks, isLoading: loading1 } = useListTasks({ status: 'completed' });
  const { data: failedTasks, isLoading: loading2 } = useListTasks({ status: 'failed' });
  const { data: conversations, isLoading: loading3 } = useListConversations();

  const isLoading = loading1 || loading2 || loading3;
  
  const conversationHistory = (conversations || []).map((c: any) => ({
    ...c,
    status: 'completed',
    description: "Multi-Agent Conversation",
    agentName: c.agentName || "Agent-01"
  }));

  const allHistory = [...(completedTasks || []), ...(failedTasks || []), ...conversationHistory]
    .sort((a: any, b: any) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());


  return (
    <Layout>
      <div className="mb-8">
        <h1 className="text-3xl font-display font-bold text-foreground">Activity</h1>
        <p className="text-muted-foreground mt-1">Timeline of completed and failed directives.</p>
      </div>

      <div className="max-w-4xl relative">
        {/* Neon timeline line */}
        <div className="absolute left-[27px] top-4 bottom-4 w-px bg-gradient-to-b from-primary/50 via-secondary/50 to-transparent" />
        
        {isLoading ? (
          <div className="pl-16 py-8 flex items-center gap-4 text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin text-primary" /> Decrypting records...
          </div>
        ) : allHistory.length === 0 ? (
          <div className="pl-16 py-8 text-muted-foreground">No historical records found.</div>
        ) : (
          <div className="space-y-6 relative z-10">
            {allHistory.map((task: any) => (
              <div key={task.id} className="flex gap-6 items-start group">
                <div className="w-14 h-14 shrink-0 rounded-full bg-background border-2 border-white/10 flex items-center justify-center relative z-10 shadow-[0_0_15px_rgba(0,0,0,0.5)] group-hover:border-primary/50 transition-colors">
                  {task.status === 'completed' ? (
                    <CheckCircle className="w-6 h-6 text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.5)]" />
                  ) : (
                    <XCircle className="w-6 h-6 text-red-400 drop-shadow-[0_0_8px_rgba(248,113,113,0.5)]" />
                  )}
                </div>
                <Card className="flex-1 p-5 shadow-lg group-hover:shadow-[0_0_30px_rgba(0,240,255,0.1)] transition-shadow">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                    <h3 className="font-display font-bold text-lg text-foreground">{task.title}</h3>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">{formatDate(task.updatedAt)}</span>
                      <Badge variant={task.status === 'completed' ? 'success' : 'error'}>{task.status}</Badge>
                    </div>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4">{task.description}</p>
                  <div className="flex items-center gap-2 text-xs font-mono text-primary/80 bg-primary/5 px-3 py-2 rounded-md border border-primary/10 inline-flex">
                    <span className="opacity-50">EXEC_BY:</span> {task.agentName}
                  </div>
                </Card>
              </div>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
