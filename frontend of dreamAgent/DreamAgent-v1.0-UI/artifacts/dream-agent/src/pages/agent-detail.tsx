import { useRoute, Link } from "wouter";
import { useGetAgent, useUpdateAgent, useListTasks } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Card, Badge, Button, Modal, Input } from "@/components/ui-elements";
import { Cpu, ArrowLeft, TerminalSquare, Activity, Settings2, Loader2, MessageSquare, CheckCircle } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { formatDate } from "@/lib/utils";
import { useForm } from "react-hook-form";

export default function AgentDetail() {
  const [, params] = useRoute("/agents/:id");
  const agentId = parseInt(params?.id || "0");
  
  const { data: agent, isLoading } = useGetAgent(agentId, { query: { enabled: !!agentId }});
  const { data: tasks, isLoading: tasksLoading } = useListTasks({ agentId }, { query: { enabled: !!agentId }});
  
  const [isEditOpen, setIsEditOpen] = useState(false);

  if (isLoading) return <Layout><div className="flex justify-center p-20"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div></Layout>;
  if (!agent) return <Layout><div className="p-8 text-center text-muted-foreground">Agent not found</div></Layout>;

  return (
    <Layout>
      <div className="mb-6">
        <Link href="/agents" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary transition-colors mb-4">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Agents
        </Link>
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary/20 to-secondary/20 border border-primary/30 flex items-center justify-center shadow-[0_0_20px_rgba(0,240,255,0.2)]">
              <Cpu className="w-8 h-8 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-display font-bold text-foreground flex items-center gap-3">
                {agent.name}
                <Badge variant={agent.status === 'active' ? 'neon' : 'default'}>{agent.status}</Badge>
              </h1>
              <p className="text-muted-foreground font-mono mt-1 text-sm">{agent.model} • Deployed {formatDate(agent.createdAt)}</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Link href={`/chat?agentId=${agent.id}`}>
              <Button variant="secondary"><MessageSquare className="w-4 h-4 mr-2" /> Comm Link</Button>
            </Link>
            <Button variant="outline" onClick={() => setIsEditOpen(true)}><Settings2 className="w-4 h-4 mr-2" /> Reconfigure</Button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-display font-semibold mb-4 border-b border-white/10 pb-2">Operational Profile</h3>
            <p className="text-muted-foreground text-sm mb-6">{agent.description}</p>
            
            <div className="space-y-4">
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Status</span>
                <span className="font-semibold text-foreground capitalize">{agent.status}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Total Tasks</span>
                <span className="font-semibold text-foreground">{agent.taskCount}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Total Comms</span>
                <span className="font-semibold text-foreground">{agent.conversationCount}</span>
              </div>
              <div className="flex justify-between items-center text-sm">
                <span className="text-muted-foreground">Last Sync</span>
                <span className="font-semibold text-foreground">{formatDate(agent.updatedAt)}</span>
              </div>
            </div>
          </Card>
        </div>

        <div className="lg:col-span-2 space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-display font-semibold mb-4 flex items-center gap-2">
              <TerminalSquare className="w-5 h-5 text-primary" />
              Base Directives (System Prompt)
            </h3>
            <div className="bg-black/50 p-4 rounded-xl border border-white/5 font-mono text-sm text-emerald-400/80 whitespace-pre-wrap">
              {agent.systemPrompt}
            </div>
          </Card>

          <Card className="p-6">
            <h3 className="text-lg font-display font-semibold mb-4 flex items-center gap-2">
              <Activity className="w-5 h-5 text-secondary" />
              Task Log
            </h3>
            {tasksLoading ? (
              <div className="p-8 text-center"><Loader2 className="w-6 h-6 animate-spin text-primary mx-auto" /></div>
            ) : !tasks || tasks.length === 0 ? (
              <div className="p-8 text-center text-muted-foreground">No tasks executed yet.</div>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                {tasks.map((task: any) => (
                  <div key={task.id} className="p-4 rounded-xl bg-white/5 border border-white/5 flex justify-between items-center">
                    <div>
                      <div className="font-semibold text-sm text-foreground">{task.title}</div>
                      <div className="text-xs text-muted-foreground mt-1">{formatDate(task.createdAt)}</div>
                    </div>
                    <Badge variant={task.status === 'completed' ? 'success' : 'default'}>{task.status}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
      
      <EditAgentModal agent={agent} isOpen={isEditOpen} onClose={() => setIsEditOpen(false)} />
    </Layout>
  );
}

function EditAgentModal({ agent, isOpen, onClose }: { agent: any, isOpen: boolean, onClose: () => void }) {
  const { register, handleSubmit } = useForm({ defaultValues: agent });
  const queryClient = useQueryClient();
  const { toast } = useToast();
  
  const { mutate, isPending } = useUpdateAgent({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: [`/api/agents/${agent.id}`] });
        queryClient.invalidateQueries({ queryKey: [`/api/agents`] });
        toast({ title: "Configuration Updated" });
        onClose();
      }
    }
  });

  const onSubmit = (data: any) => {
    mutate({ id: agent.id, data: {
      name: data.name,
      description: data.description,
      model: data.model,
      status: data.status,
      systemPrompt: data.systemPrompt
    }});
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Reconfigure Agent">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Name</label>
          <Input {...register("name")} />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Status</label>
          <select 
            {...register("status")}
            className="flex h-11 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary appearance-none"
          >
            <option value="active">Active</option>
            <option value="idle">Idle</option>
            <option value="paused">Paused</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">System Prompt</label>
          <textarea 
            {...register("systemPrompt")}
            className="flex min-h-[150px] w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
          />
        </div>
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={isPending}>
            {isPending ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null} Save Changes
          </Button>
        </div>
      </form>
    </Modal>
  );
}
