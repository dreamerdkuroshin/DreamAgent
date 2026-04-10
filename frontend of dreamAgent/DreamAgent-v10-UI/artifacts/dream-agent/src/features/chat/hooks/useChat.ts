import { useState, useCallback, useRef } from "react";
import { useStreaming } from "./useStreaming";
import { useQueryClient } from "@tanstack/react-query";

export type MessageStatus = "thinking" | "running" | "completed" | "error" | "idle" | "cancelled";

export type AgentStep = {
  type: string;
  task_id?: string;
  content: string;
  tool?: string;
  agent?: string;
  status?: string;
};

export type LiveMessage = {
  role: "assistant";
  content: string;
  status: MessageStatus;
  steps: AgentStep[];
  id: string;
  error?: string;
};

/**
 * Maps SSE event type to a UI-facing message status.
 * This drives the status badge on AgentMessage.
 */
function mapEventToStatus(type: string): MessageStatus {
  if (type === "start") return "running";
  if (type === "final") return "completed";
  if (type === "error") return "error";
  return "thinking"; // plan, tool, result, agent, reflection all indicate active work
}

export function useChat(activeConvoId: number | null, setMsgInput: (v: string) => void) {
  const queryClient = useQueryClient();
  const { isStreaming, errorMsg, setErrorMsg, startStream, cancelStream: cancelStreamHook } = useStreaming();

  const [liveMessage, setLiveMessage] = useState<LiveMessage | null>(null);
  const taskIdRef = useRef<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);

  const cancelStream = useCallback(async () => {
    // 1. Stop the EventSource locally
    cancelStreamHook();

    // 2. ✅ Notify the backend to cancel the running task
    const taskId = taskIdRef.current;
    if (taskId) {
      try {
        await fetch(`/api/v1/chat/stream/${taskId}`, { method: "DELETE" });
      } catch (e) {
        console.warn("Backend cancel request failed (task may already be complete):", e);
      }
    }
    taskIdRef.current = null;
    setLiveMessage(prev => prev ? { ...prev, status: "cancelled" } : null);
  }, [cancelStreamHook]);

  const sendMessage = useCallback(
    async (prompt: string, provider: string = "auto", model: string = "", files?: File[]) => {
      let finalPrompt = prompt;
      let uploadedDocIds: string[] = [];

      if (!finalPrompt.trim() && !files?.length) return;
      if (!activeConvoId || isStreaming) return;

      setMsgInput("");

      const newTaskId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
      taskIdRef.current = newTaskId;
      setTaskId(newTaskId);

      setLiveMessage({
        id: newTaskId,
        role: "assistant",
        content: files?.length ? `Uploading ${files.length} file(s)...` : "",
        status: "thinking",
        steps: [],
      });

      // 1. Parallel File Uploads (5-10x performance boost before chat triggers)
      if (files?.length) {
        try {
          const uploadPromises = files.map(file => {
            const formData = new FormData();
            formData.append("file", file);
            formData.append("bot_id", "local_gui");
            formData.append("user_id", "web_client");
            return fetch('/api/v1/files/upload', {
              method: "POST",
              body: formData
            }).then(res => res.json());
          });

          const results = await Promise.all(uploadPromises);
          // Collect verified doc_ids
          uploadedDocIds = results.map(r => r.doc_id).filter(id => id);
          finalPrompt += `\n\n[System Note: User uploaded ${uploadedDocIds.length} files. IDs: ${uploadedDocIds.join(",")} ]`;
        } catch (e) {
          console.error("[Chat] Upload error", e);
          setLiveMessage(prev => prev ? { ...prev, content: "❌ Document upload failed.", status: "error" } : null);
          return;
        }
      }

      setLiveMessage(prev => prev ? { ...prev, content: "" } : null);

      const url = `/api/v1/chat/stream?query=${encodeURIComponent(finalPrompt)}&taskId=${newTaskId}&convoId=${activeConvoId}&provider=${provider}&model=${model}&file_ids=${uploadedDocIds.join(",")}`;

      startStream(
        url,
        (data: any) => {
          setLiveMessage((prev) => {
            if (!prev) return prev;

            const next = { ...prev };

            if (data.type === "user_persisted") {
              // The backend has synchronously saved the user's message
              // Tell React Query to fetch the DB copy so the UI has it right away
              queryClient.refetchQueries({ queryKey: [`/api/conversations/${activeConvoId}/messages`] })
                .then(() => {
                  window.dispatchEvent(new CustomEvent("chat:user_persisted"));
                });
              return prev; // No state change to liveMessage needed
            } else if (data.type === "token") {
              // 🔥 Real token streaming — append each chunk as it arrives (ChatGPT-style)
              next.content += data.content || "";
              next.status = "running";
            } else if (data.type === "builder_form") {
              // 🏗️ Backend wants to show the inline builder form widget in chat
              window.dispatchEvent(new CustomEvent("builder:form", { detail: true }));
              next.status = "completed";
            } else if (data.type === "builder_message") {
              // 🏗️ Structured builder step message (replaces raw text)
              next.content = data.message || data.content || next.content;
              next.status = "running";
            } else if (data.type === "builder_step") {
              if (data.session_id) {
                window.dispatchEvent(new CustomEvent("builder:session", { detail: data.session_id }));
              }
              // Dispatch progress to builder panel overlay
              window.dispatchEvent(new CustomEvent("builder:progress", { detail: { progress: data.progress, message: data.message || data.step } }));

              // 🏗️ Live build progress — show real-time steps in the chat bubble
              const stepText = `⚙️ ${data.message || data.step} (${data.progress || 0}%)`;
              if (!next.content.includes("🏗️ Building")) {
                next.content = "🏗️ Building your project...\n\n";
              }
              // Replace the last progress line or append
              const lines = next.content.split("\n");
              const lastLine = lines[lines.length - 1];
              if (lastLine.startsWith("⚙️")) {
                lines[lines.length - 1] = stepText;
              } else {
                lines.push(stepText);
              }
              next.content = lines.join("\n");
              next.status = "running";
            } else if (data.type === "final") {
              // Final signal — tokens already accumulated via type=token
              // If backend sends content here (non-streaming fallback), use it
              if (data.content) {
                next.content = data.content;
              }
              next.status = "completed";
              // NEW: Persist the msg ID if the backend reports it saved synchronously
              if (data.msg_id) {
                (next as any).db_msg_id = data.msg_id;
              }
            } else if (data.type === "error") {
              next.content = "❌ " + (data.content || "Error");
              next.status = "error";
            } else {
              // Silently accumulate trace steps (plan, step, thinking, agent, etc.)
              // Kept internally for trace panel — never shown in chat bubble
              next.steps = [...next.steps, data];
              next.status = mapEventToStatus(data.type);
            }

            return next;
          });
        },
        async () => {
          // Stream completed — force a refetch to ensure DB has the message
          try {
            await queryClient.refetchQueries({ queryKey: [`/api/conversations/${activeConvoId}/messages`] });
          } catch (e) {
            console.error("Failed to refetch messages", e);
          }
          taskIdRef.current = null;
          // We intentionally don't clear setTaskId(null) here so the trace panel can stay open 
          // Since refetchQueries is complete, the DB message is parsed. 
          // Small buffer to allow React to render the new message before unmounting the live one
          setTimeout(() => setLiveMessage(null), 150);
        }
      );
    },
    [activeConvoId, isStreaming, startStream, setMsgInput, queryClient]
  );

  return {
    liveMessage,
    isStreaming,
    errorMsg,
    sendMessage,
    cancelStream,
    taskId,
  };
}
