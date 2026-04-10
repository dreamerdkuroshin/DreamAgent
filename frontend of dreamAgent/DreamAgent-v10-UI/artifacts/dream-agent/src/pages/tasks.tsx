import { useState } from "react";
import { useListTasks, useListAgents, useCreateTask, useUpdateTask } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Card, Button, Badge, Modal, Input } from "@/components/ui-elements";
import { CheckSquare, Plus, Loader2, Play, Check, XCircle } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useForm } from "react-hook-form";
import { useToast } from "@/hooks/use-toast";

export default function Tasks() {
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const { data: tasks, isLoading } = useListTasks(statusFilter ? { status: statusFilter as any } : {});
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { mutate: updateTask } = useUpdateTask({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["/api/v1/tasks"] });
        queryClient.invalidateQueries({ queryKey: ["/api/v1/stats"] });
        toast({ title: "Task Status Updated" });
      }
    }
  });

  return (
    <Layout>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">Task Queue</h1>
          <p className="text-muted-foreground mt-1">Monitor and deploy agent tasks.</p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="w-4 h-4 mr-2" /> Deploy Task
        </Button>
      </div>

      <div className="mb-6 flex gap-2 overflow-x-auto pb-2">
        {['', 'pending', 'running', 'completed', 'failed'].map(status => (
          <button
            key={status}
            onClick={() => setStatusFilter(status)}
            className={`px-4 py-1.5 rounded-full text-sm font-semibold border transition-all ${
              statusFilter === status 
                ? "bg-primary/20 border-primary text-primary neon-border" 
                : "bg-black/40 border-white/10 text-muted-foreground hover:bg-white/5"
            }`}
          >
            {status || 'All Tasks'}
          </button>
        ))}
      </div>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs text-muted-foreground uppercase bg-black/40 border-b border-white/10">
              <tr>
                <th className="px-6 py-4 font-semibold">Directive</th>
                <th className="px-6 py-4 font-semibold">Operative</th>
                <th className="px-6 py-4 font-semibold">Status</th>
                <th className="px-6 py-4 font-semibold">Priority</th>
                <th className="px-6 py-4 font-semibold">Deployed</th>
                <th className="px-6 py-4 font-semibold text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={6} className="px-6 py-12 text-center"><Loader2 className="w-6 h-6 animate-spin mx-auto text-primary" /></td></tr>
              ) : tasks?.length === 0 ? (
                <tr><td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">No tasks found matching criteria.</td></tr>
              ) : (
                tasks?.map(task => (
                  <tr key={task.id} className="border-b border-white/5 bg-transparent hover:bg-white/[0.02] transition-colors">
                    <td className="px-6 py-4 font-medium text-foreground">{task.title}</td>
                    <td className="px-6 py-4 text-muted-foreground">{task.agentName}</td>
                    <td className="px-6 py-4">
                       <Badge variant={
                          task.status === "completed" ? "success" : 
                          task.status === "running" ? "neon" : 
                          task.status === "failed" ? "error" : "warning"
                        }>
                          {task.status}
                        </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <span className={`text-xs px-2 py-1 rounded-md bg-white/5 ${
                        task.priority === 'critical' ? 'text-red-400' : 
                        task.priority === 'high' ? 'text-amber-400' : 'text-foreground'
                      }`}>
                        {task.priority.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-muted-foreground">{formatDate(task.createdAt)}</td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        {task.status === 'pending' && (
                          <Button variant="outline" className="px-2 py-1 h-8 text-xs border-primary text-primary" onClick={() => updateTask({ id: task.id, data: { status: 'running' } })}>
                            <Play className="w-3 h-3 mr-1" /> Start
                          </Button>
                        )}
                        {task.status === 'running' && (
                          <Button variant="outline" className="px-2 py-1 h-8 text-xs border-emerald-500 text-emerald-500" onClick={() => updateTask({ id: task.id, data: { status: 'completed' } })}>
                            <Check className="w-3 h-3 mr-1" /> Finish
                          </Button>
                        )}
                        {(task.status === 'pending' || task.status === 'running') && (
                          <Button variant="ghost" className="px-2 py-1 h-8 text-xs text-red-400 hover:text-red-300" onClick={() => updateTask({ id: task.id, data: { status: 'failed' } })}>
                            <XCircle className="w-3 h-3" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      <CreateTaskModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
    </Layout>
  );
}

function CreateTaskModal({ isOpen, onClose }: { isOpen: boolean, onClose: () => void }) {
  const { data: agents } = useListAgents();
  const { register, handleSubmit, reset } = useForm();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { mutate, isPending } = useCreateTask({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["/api/v1/tasks"] });
        queryClient.invalidateQueries({ queryKey: ["/api/v1/stats"] });
        toast({ title: "Task Deployed" });
        reset();
        onClose();
      }
    }
  });

  const onSubmit = (data: any) => mutate({ data: { ...data, agentId: parseInt(data.agentId) } });

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Deploy Task Directive">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Task Title</label>
          <Input {...register("title", { required: true })} placeholder="e.g. Analyze Q3 Data" />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Description</label>
          <textarea 
            {...register("description", { required: true })}
            className="flex min-h-[80px] w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Assign Operative</label>
            <select 
              {...register("agentId", { required: true })}
              className="flex h-11 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary appearance-none"
            >
              {agents?.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-muted-foreground mb-1">Priority</label>
            <select 
              {...register("priority", { required: true })}
              className="flex h-11 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary appearance-none"
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-4">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={isPending}>
            {isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />} Deploy
          </Button>
        </div>
      </form>
    </Modal>
  );
}
