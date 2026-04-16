import { cn } from "@/lib/utils";
import { AgentMessage } from "../agent-ui/AgentMessage";
import { User } from "lucide-react";

interface MessageBubbleProps {
  message: {
    id: number | string;
    role: "user" | "assistant";
    content: string;
    steps?: any[];
    status?: string;
    error?: string;
  };
  isStreaming?: boolean;
}

export function MessageBubble({ message, isStreaming = false }: MessageBubbleProps) {
  const isUser = message.role === "user";

  if (!isUser) {
    return <AgentMessage message={message} isStreaming={isStreaming} />;
  }

  return (
    <div className="flex max-w-[85%] ml-auto justify-end mb-4 animate-in fade-in slide-in-from-right-4 duration-500 group">
      <div className="flex flex-col items-end gap-2">
        <div className="flex items-center gap-2 text-[10px] font-bold text-primary/60 uppercase tracking-widest mr-1">
          Operative Commander <User className="w-3 h-3" />
        </div>
        <div className="p-4 rounded-2xl bg-primary/10 text-foreground border border-primary/20 rounded-br-none shadow-lg shadow-primary/5 transition-all hover:border-primary/40">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{message.content}</p>
        </div>
      </div>
    </div>
  );
}
