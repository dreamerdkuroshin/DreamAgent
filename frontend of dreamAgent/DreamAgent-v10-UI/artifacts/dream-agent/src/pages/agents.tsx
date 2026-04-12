import { useState } from "react";
import { useListAgents, useCreateAgent, useDeleteAgent, useListModels } from "@workspace/api-client-react";
import { useQueryClient } from "@tanstack/react-query";
import { Layout } from "@/components/layout";
import { Card, Button, Badge, Modal, Input } from "@/components/ui-elements";
import {
  Cpu, Plus, Search, Trash2, Eye, MessageSquare, Loader2,
  Network, Brain, Zap, ShieldCheck, GitBranch, Code2, FlaskConical,
  PenLine, BookOpen
} from "lucide-react";
import { Link } from "wouter";
import { useToast } from "@/hooks/use-toast";
import { useForm } from "react-hook-form";
import { cn } from "@/lib/utils";

export const AGENT_TYPES = [
  { value: "Orchestrator", label: "Orchestrator", icon: Network, color: "text-primary", description: "Coordinates planner + workers across complex multi-step tasks" },
  { value: "Planner", label: "Planner", icon: Brain, color: "text-secondary", description: "Decomposes goals into ordered executable steps" },
  { value: "Worker", label: "Worker", icon: Zap, color: "text-amber-400", description: "Executes steps via AutoGPT + ReAct loop" },
  { value: "Validator", label: "Validator", icon: ShieldCheck, color: "text-emerald-400", description: "Reviews and validates agent outputs for quality" },
  { value: "Debate", label: "Debate", icon: GitBranch, color: "text-violet-400", description: "Ensemble reasoning via multi-perspective debate" },
  { value: "Research", label: "Research", icon: BookOpen, color: "text-sky-400", description: "v6: Gathers data via search, YouTube, and browser" },
  { value: "Writer", label: "Writer", icon: PenLine, color: "text-pink-400", description: "v6: Content generation, synthesis, and tone shaping" },
  { value: "Coder", label: "Coder", icon: Code2, color: "text-lime-400", description: "v8: Autonomous dev — reads/writes code, runs tests, git" },
  { value: "Critic", label: "Critic", icon: FlaskConical, color: "text-orange-400", description: "v6: Self-reflection and quality control evaluator" },
];

// Hardcoded models are now replaced by useListModels() in CreateAgentModal

export default function Agents() {
  const [searchTerm, setSearchTerm] = useState("");
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [filterType, setFilterType] = useState<string | null>(null);
  const { data: agents, isLoading } = useListAgents();

  const filteredAgents = (agents || []).filter((a: any) => {
    const matchSearch = a.name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchSearch;
  });

  return (
    <Layout>
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-6 gap-4">
        <div>
          <h1 className="text-3xl font-display font-bold text-foreground">AI Agents</h1>
          <p className="text-muted-foreground mt-1">9 specialized agent types — your complete autonomous workforce.</p>
        </div>
        <Button onClick={() => setIsCreateOpen(true)}>
          <Plus className="w-4 h-4 mr-2" /> New Agent
        </Button>
      </div>

      {/* Type legend */}
      <div className="flex flex-wrap gap-2 mb-5">
        <button
          onClick={() => setFilterType(null)}
          className={cn("flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-all",
            filterType === null ? "border-primary/40 bg-primary/10 text-primary" : "border-white/5 text-muted-foreground hover:border-white/10"
          )}
        >All</button>
        {AGENT_TYPES.map((t: any) => (
          <button key={t.value}
            onClick={() => setFilterType(filterType === t.value ? null : t.value)}
            className={cn("flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border transition-all",
              filterType === t.value ? `border-white/20 bg-white/5 ${t.color}` : "border-white/5 text-muted-foreground hover:border-white/10"
            )}
          >
            <t.icon className={cn("w-3 h-3", filterType === t.value ? t.color : "")} />
            {t.value}
          </button>
        ))}
      </div>

      <div className="mb-6 relative">
        <Search className="w-5 h-5 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
        <Input placeholder="Search agents..." className="pl-10 max-w-md"
          value={searchTerm} onChange={e => setSearchTerm(e.target.value)} />
      </div>

      {isLoading ? (
        <div className="flex justify-center p-20"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div>
      ) : filteredAgents.length === 0 ? (
        <div className="text-center py-20 glass-panel rounded-2xl">
          <Cpu className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <h3 className="text-lg font-medium text-foreground">No agents found</h3>
          <p className="text-muted-foreground mt-2">Create your first specialized agent to get started.</p>
          <Button className="mt-4" onClick={() => setIsCreateOpen(true)}><Plus className="w-4 h-4 mr-2" />Create Agent</Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
          {filteredAgents.map((agent: any) => <AgentCard key={agent.id} agent={agent} />)}
        </div>
      )}

      <CreateAgentModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
    </Layout>
  );
}

function AgentCard({ agent }: { agent: any }) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { mutate: deleteAgent, isPending: isDeleting } = useDeleteAgent({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["/api/v1/agents"] });
        toast({ title: "Agent removed" });
      }
    }
  });

  const typeInfo = AGENT_TYPES.find(t => t.value === agent.type) || AGENT_TYPES.find(t => t.value === agent.name.split(" ")[0]) || AGENT_TYPES[2];
  const IconComp = typeInfo.icon;

  const stateColor: any = ({
    active: "neon", idle: "default", paused: "warning",
    thinking: "neon", executing: "warning", error: "error",
  } as any)[agent.status] || "default";

  return (
    <Card className="p-5 flex flex-col h-full group hover:border-white/10 transition-colors">
      <div className="flex justify-between items-start mb-4">
        <div className="flex items-center gap-3">
          <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center border",
            "bg-black/30 border-white/5 group-hover:border-white/10 transition-colors")}>
            <IconComp className={cn("w-5 h-5", typeInfo.color)} />
          </div>
          <div>
            <h3 className="font-display font-bold text-sm text-foreground leading-tight">{agent.name}</h3>
            <p className="text-xs font-mono text-muted-foreground mt-0.5">{agent.model_name || agent.model}</p>
          </div>
        </div>
        <Badge variant={stateColor}>{agent.status}</Badge>
      </div>

      <div className={cn("text-xs px-2 py-1 rounded-full w-fit mb-3 font-medium", typeInfo.color, "bg-current/10")}>
        <span style={{ color: "inherit" }} className={cn("opacity-100", typeInfo.color)}>{typeInfo.value}</span>
      </div>

      <p className="text-sm text-muted-foreground flex-1 mb-4 line-clamp-2">{agent.description}</p>

      <div className="grid grid-cols-2 gap-2 mb-4">
        <div className="bg-black/30 p-2.5 rounded-lg border border-white/5 text-center">
          <div className="text-xs text-muted-foreground">Tasks</div>
          <div className="font-bold text-sm text-foreground">{agent.task_count ?? agent.taskCount ?? 0}</div>
        </div>
        <div className="bg-black/30 p-2.5 rounded-lg border border-white/5 text-center">
          <div className="text-xs text-muted-foreground">Chats</div>
          <div className="font-bold text-sm text-foreground">{agent.conversation_count ?? agent.conversationCount ?? 0}</div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-white/10">
        <div className="flex gap-1">
          <Link href={`/chat?agentId=${agent.id}`} className="p-2 text-muted-foreground hover:text-primary hover:bg-primary/10 rounded-lg transition-colors">
            <MessageSquare className="w-4 h-4" />
          </Link>
          <Link href={`/agents/${agent.id}`} className="p-2 text-muted-foreground hover:text-white hover:bg-white/10 rounded-lg transition-colors">
            <Eye className="w-4 h-4" />
          </Link>
        </div>
        <button 
          onClick={() => deleteAgent({ id: agent.id })}
          disabled={isDeleting}
          className="p-2 text-muted-foreground hover:text-red-400 hover:bg-red-400/10 rounded-lg transition-colors"
          title="Delete Agent"
        >
          {isDeleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
        </button>
      </div>
    </Card>
  );
}

function CreateAgentModal({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  const { register, handleSubmit, reset, watch } = useForm({ 
    defaultValues: { 
      name: "",
      description: "",
      agentType: "Worker", 
      model: "",
      systemPrompt: ""
    } 
  });
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { data: modelData } = useListModels();
  const selectedType = watch("agentType");
  const selectedTypeInfo = AGENT_TYPES.find(t => t.value === selectedType) || AGENT_TYPES[2];

  // Set default model once loaded
  const hasSetDefault = useState(false);
  if (modelData?.default_model && !watch("model") && !hasSetDefault[0]) {
    reset({ ...watch(), model: modelData.default_model });
    hasSetDefault[1](true);
  }

  const { mutate, isPending } = useCreateAgent({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ["/api/v1/agents"] });
        queryClient.invalidateQueries({ queryKey: ["/api/stats"] });
        toast({ title: "Agent created", description: `${selectedType} agent is ready.` });
        reset();
        onClose();
      }
    }
  });

  const onSubmit = (data: any) => {
    mutate({
      data: {
        name: data.name,
        type: data.agentType,
        description: data.description || selectedTypeInfo.description,
        model: data.model,
        systemPrompt: data.systemPrompt || `You are a ${data.agentType} agent. ${selectedTypeInfo.description}`,
      }
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Create New Agent">
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-2">Agent Type</label>
          <div className="grid grid-cols-3 gap-2">
            {AGENT_TYPES.map((t: any) => (
              <label key={t.value} className={cn(
                "flex flex-col items-center gap-1.5 p-3 rounded-xl border cursor-pointer text-center transition-all",
                selectedType === t.value
                  ? `border-white/20 bg-white/5 ${t.color}`
                  : "border-white/5 text-muted-foreground hover:border-white/10"
              )}>
                <input type="radio" value={t.value} {...register("agentType")} className="hidden" />
                <t.icon className={cn("w-4 h-4", selectedType === t.value ? t.color : "")} />
                <span className="text-xs font-medium">{t.value}</span>
              </label>
            ))}
          </div>
          {selectedTypeInfo && (
            <p className="mt-2 text-xs text-muted-foreground px-1">{selectedTypeInfo.description}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Name</label>
          <Input {...register("name", { required: true })} placeholder={`e.g. ${selectedType || "Worker"}-01`} />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Description</label>
          <Input {...register("description")} placeholder="What this agent specializes in..." />
        </div>
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">Model</label>
          <select {...register("model", { required: true })}
            className="flex h-11 w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary">
            {modelData?.providers?.map((p: any) => (
              <optgroup key={p.id} label={`${p.icon} ${p.name}`}>
                {p.models.map((m: any) => (
                  <option key={m.id} value={m.id}>{m.name} ({m.tag})</option>
                ))}
              </optgroup>
            ))}
            {!modelData?.providers?.length && (
              <option disabled>No models available (check API keys)</option>
            )}
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium text-muted-foreground mb-1">System Prompt</label>
          <textarea {...register("systemPrompt")}
            className="flex min-h-[80px] w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:border-primary resize-none"
            placeholder={`You are a ${selectedType || "Worker"} agent...`} />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={isPending}>
            {isPending && <Loader2 className="w-4 h-4 animate-spin mr-2" />} Create Agent
          </Button>
        </div>
      </form>
    </Modal>
  );
}
